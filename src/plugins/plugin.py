import importlib
import shutil
import sys
import tempfile
import webbrowser
import zipfile
from pathlib import Path
from urllib.request import urlopen

import yaml
from PySide6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

import src.config as config

# keep references to open plugin dialogs so they aren't garbage-collected
_open_dialogs = {}


def _fail(parent, message, title="Install failed"):
    QMessageBox.warning(parent, title, message)


def _refresh_page(page):
    if page is None:
        return
    # deferred import: tools_loader imports src.plugins, so we'd loop at module load
    from src.tools_loader import load_tools_for_page
    load_tools_for_page(page)


def install_tool(tid, url, page=None):
    parent = page  # used as QMessageBox parent; None is fine

    if not url:
        _fail(parent, f"No download URL for {tid}")
        return

    plugins_dir = config.plugins_dir
    plugins_dir.mkdir(parents=True, exist_ok=True)

    # 1. download to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".lamp", delete=False)
    download_failed = None
    try:
        with urlopen(url) as resp:
            shutil.copyfileobj(resp, tmp)
    except Exception as exc:
        download_failed = exc
    finally:
        tmp.close()  # release the Windows file lock

    tmp_path = Path(tmp.name)

    if download_failed is not None:
        tmp_path.unlink(missing_ok=True)
        _fail(parent, f"Download failed: {download_failed}")
        return

    try:
        # 2. validate it's actually a zip
        if not zipfile.is_zipfile(tmp_path):
            _fail(parent, f"{tid}: download is not a valid zip")
            return

        # 3. read plugin.yaml manifest BEFORE extracting anything
        try:
            with zipfile.ZipFile(tmp_path) as zf:
                with zf.open("plugin.yaml") as mf:
                    manifest = yaml.safe_load(mf) or {}
        except KeyError:
            _fail(parent, "Bundle is missing plugin.yaml")
            return
        except yaml.YAMLError as exc:
            _fail(parent, f"Bad plugin.yaml in bundle:\n{exc}")
            return

        # 4. confirm the bundle's id matches what we asked for
        manifest_id = manifest.get("id")
        if manifest_id != tid:
            _fail(
                parent,
                f"Bundle id mismatch: expected '{tid}', got '{manifest_id}'",
            )
            return

        # 5. compatibility check (simple exact-or-missing match for now)
        required_app = (manifest.get("requires") or {}).get("app")
        if required_app and required_app != config.ver:
            _fail(
                parent,
                f"Plugin requires app {required_app}, running {config.ver}",
            )
            return

        # 6. atomic install: extract to staging, then rename onto target
        target = plugins_dir / str(tid)
        staging = plugins_dir / f".{tid}.partial"
        if staging.exists():
            shutil.rmtree(staging)

        try:
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(staging)
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            _fail(parent, f"Extract failed: {exc}")
            return

        # only touch the real install dir once staging succeeded
        if target.exists():
            shutil.rmtree(target)
        staging.rename(target)
    finally:
        tmp_path.unlink(missing_ok=True)

    # 7. refresh the page so the button flips from "Install" to "Open"
    _refresh_page(page)

def _raise_existing_dialog(tid):
    existing = _open_dialogs.get(tid)
    if existing is None:
        return False
    existing.show()
    existing.raise_()
    existing.activateWindow()
    return True


def _show_plugin_dialog(tid, title, widget, page):
    dlg = QDialog(page)
    dlg.setWindowTitle(title)
    dlg_layout = QVBoxLayout(dlg)
    dlg_layout.setContentsMargins(0, 0, 0, 0)
    dlg_layout.addWidget(widget)
    dlg.resize(800, 600)
    dlg.finished.connect(lambda _result, k=tid: _open_dialogs.pop(k, None))
    _open_dialogs[tid] = dlg
    dlg.show()


def _build_python_plugin_widget(plugin_dir, entry, page):
    """Returns (widget, error_message). On success, error_message is None."""
    module_name = entry.get("module")
    builder_name = entry.get("builder", "build")
    if not module_name:
        return None, "Plugin manifest is missing entry.module"

    src_root = str(plugin_dir / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    try:
        # hot-reload: if the module's already imported, refresh it so edits land
        if module_name in sys.modules:
            module = importlib.reload(sys.modules[module_name])
        else:
            module = importlib.import_module(module_name)
    except Exception as exc:
        return None, f"Plugin import failed:\n{exc}"

    builder = getattr(module, builder_name, None)
    if builder is None:
        return None, f"Plugin has no '{builder_name}' function"

    try:
        return builder(page), None
    except Exception as exc:
        return None, f"Plugin failed to start:\n{exc}"


def _build_webview_plugin_widget(entry):
    """Returns (widget, error_message). Lazy-imports QWebEngineView."""
    url = entry.get("url")
    if not url:
        return None, "Webview plugin manifest is missing entry.url"

    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtCore import QUrl
    except ImportError as exc:
        return None, f"WebView support is unavailable:\n{exc}"

    view = QWebEngineView()
    view.load(QUrl(url))
    return view, None


def open_tool(tid, fields=None, page=None):
    fields = fields or {}

    # 1. catalog-level web tool — hand off to the OS default browser
    web_url = fields.get("web_url")
    if web_url:
        webbrowser.open(web_url)
        return

    # 2. already open? raise the existing window instead of stacking copies
    if _raise_existing_dialog(tid):
        return

    # 3. installed local plugin
    plugin_dir = config.plugins_dir / str(tid)
    if not plugin_dir.is_dir():
        _fail(page, f"{tid} is not installed.", title="Open failed")
        return

    manifest_path = plugin_dir / "plugin.yaml"
    if not manifest_path.is_file():
        _fail(page, "Plugin is missing plugin.yaml — try reinstalling.", title="Open failed")
        return

    try:
        with manifest_path.open("r", encoding="utf-8") as fp:
            manifest = yaml.safe_load(fp) or {}
    except yaml.YAMLError as exc:
        _fail(page, f"Bad plugin.yaml:\n{exc}", title="Open failed")
        return

    entry = manifest.get("entry") or {}
    kind = entry.get("kind")

    if kind == "python":
        widget, err = _build_python_plugin_widget(plugin_dir, entry, page)
    elif kind == "webview":
        widget, err = _build_webview_plugin_widget(entry)
    else:
        _fail(page, f"Unsupported plugin kind: {kind!r}", title="Open failed")
        return

    if err is not None:
        _fail(page, err, title="Open failed")
        return

    _show_plugin_dialog(tid, manifest.get("name", tid), widget, page)
