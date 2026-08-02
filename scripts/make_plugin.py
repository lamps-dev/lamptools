"""
Interactive scaffolder for LampTools plugins.

Run from the repo root:
    uv run python scripts/make_plugin.py

Produces a plugin source directory under ./plugins_src/<id>/ and optionally
zips it into a .lamp bundle ready to drop on a download URL.
"""

import re
import shutil
import sys
import zipfile
from pathlib import Path

import yaml


PYTHON_STARTERS = {
    "empty": """\
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


def build(parent=None):
    w = QWidget(parent)
    layout = QVBoxLayout(w)
    layout.addWidget(QLabel("Hello from __PLUGIN_NAME__"))
    return w
""",
    "text_io": """\
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
)


def build(parent=None):
    w = QWidget(parent)
    layout = QVBoxLayout(w)

    layout.addWidget(QLabel("Input"))
    input_edit = QPlainTextEdit()
    layout.addWidget(input_edit)

    button_row = QHBoxLayout()
    process_btn = QPushButton("Process")
    button_row.addStretch(1)
    button_row.addWidget(process_btn)
    layout.addLayout(button_row)

    layout.addWidget(QLabel("Output"))
    output_edit = QPlainTextEdit()
    output_edit.setReadOnly(True)
    layout.addWidget(output_edit)

    def on_click():
        # TODO: put your transformation here
        output_edit.setPlainText(input_edit.toPlainText())

    process_btn.clicked.connect(on_click)
    return w
""",
    "form": """\
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QLabel,
)


def build(parent=None):
    w = QWidget(parent)
    outer = QVBoxLayout(w)

    form = QFormLayout()
    name_edit = QLineEdit()
    note_edit = QLineEdit()
    form.addRow("Name:", name_edit)
    form.addRow("Note:", note_edit)
    outer.addLayout(form)

    result = QLabel("")
    outer.addWidget(result)

    submit_btn = QPushButton("Submit")
    outer.addWidget(submit_btn)

    def on_submit():
        result.setText(name_edit.text() + ": " + note_edit.text())

    submit_btn.clicked.connect(on_submit)
    return w
""",
    "stacked": """\
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
    QLabel,
)


def _make_page(title):
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.addWidget(QLabel(title))
    return page


def build(parent=None):
    w = QWidget(parent)
    outer = QHBoxLayout(w)

    nav = QVBoxLayout()
    stack = QStackedWidget()
    for label in ("Page A", "Page B", "Page C"):
        idx = stack.addWidget(_make_page(label))
        btn = QPushButton(label)
        btn.clicked.connect(lambda _=False, i=idx: stack.setCurrentIndex(i))
        nav.addWidget(btn)
    nav.addStretch(1)

    outer.addLayout(nav)
    outer.addWidget(stack, 1)
    return w
""",
}


def ask(prompt, default=None, required=False):
    suffix = f" [{default}]" if default else ""
    while True:
        answer = input(f"{prompt}{suffix}: ").strip()
        if answer:
            return answer
        if default is not None:
            return default
        if not required:
            return ""
        print("  (a value is required)")


def ask_choice(prompt, choices, default=None):
    print(prompt)
    for i, c in enumerate(choices, 1):
        marker = "  (default)" if c == default else ""
        print(f"  {i}. {c}{marker}")
    while True:
        raw = input("> ").strip()
        if not raw and default is not None:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(choices):
            return choices[int(raw) - 1]
        if raw in choices:
            return raw
        print("  (enter a number or one of the option names)")


def ask_yes_no(prompt, default=False):
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        raw = input(f"{prompt}{suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  (please answer y or n)")


def slugify(s):
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def page_widget_name(page_stem):
    # "audio_tools" -> "AudioToolsPage"  (matches tools_loader's reverse mapping)
    return "".join(p.title() for p in page_stem.split("_")) + "Page"


TOOLS_DIR = Path("src/tools")


def main():
    print("=" * 50)
    print(" LampTools plugin scaffolder")
    print("=" * 50)

    # --- metadata ---
    print("\n-- Metadata --")
    raw_id = ask("Plugin id (snake_case, must match catalog entry)", required=True)
    plugin_id = slugify(raw_id)
    if plugin_id != raw_id:
        print(f"  (normalised to '{plugin_id}')")

    name = ask("Display name", default=plugin_id.replace("_", " ").title())
    version = ask("Version", default="1.0.0")
    owner = ask("Owner", default="")
    about = ask("Short description", default="")
    homepage = ask("Homepage URL (optional)", default="")
    requires_app = ask("Requires app version, e.g. v1.0 (optional)", default="")

    # --- page ---
    print("\n-- Page --")
    existing_pages = []
    if TOOLS_DIR.is_dir():
        existing_pages = sorted(p.stem for p in TOOLS_DIR.glob("*.yaml"))

    if existing_pages:
        options = existing_pages + ["(new page)"]
        picked = ask_choice(
            "Which page should this plugin appear on?",
            options,
            default=existing_pages[0],
        )
        if picked == "(new page)":
            page_name = slugify(
                ask("New page yaml stem (e.g. audio_tools)", required=True)
            )
        else:
            page_name = picked
    else:
        page_name = slugify(
            ask("Page yaml stem (e.g. text_tools)", required=True)
        )

    is_new_page = page_name not in existing_pages
    if is_new_page:
        print(
            f"  Note: for this page to render in the GUI you also need a"
            f" QWidget named '{page_widget_name(page_name)}' in the"
            f" stackedWidget (case-sensitive)."
        )

    # --- kind ---
    print("\n-- Plugin kind --")
    kind = ask_choice(
        "What does this plugin embed?",
        ["python", "webview"],
        default="python",
    )

    entry = {"kind": kind}
    starter = None

    if kind == "webview":
        print("\n-- Webview --")
        entry["url"] = ask("URL to load", required=True)
    else:
        print("\n-- Python plugin --")
        entry["module"] = ask("Python module name", default=plugin_id)
        entry["builder"] = ask("Builder function", default="build")

        print(
            "\nStarter templates:\n"
            "  empty    - blank widget with a Hello label\n"
            "  text_io  - input box + Process button + output box\n"
            "  form     - labelled fields + Submit\n"
            "  stacked  - sidebar buttons swapping a QStackedWidget"
        )
        starter = ask_choice(
            "Pick a starter:",
            list(PYTHON_STARTERS.keys()),
            default="empty",
        )

    # --- manifest ---
    manifest = {
        "id": plugin_id,
        "name": name,
        "version": version,
        "entry": entry,
    }
    if owner:
        manifest["owner"] = owner
    if about:
        manifest["about"] = about
    if homepage:
        manifest["homepage"] = homepage
    if requires_app:
        manifest["requires"] = {"app": requires_app}

    # --- output ---
    print("\n-- Output --")
    default_out = f"./plugins_src/{plugin_id}"
    out_dir = Path(ask("Output directory", default=default_out)).resolve()

    if out_dir.exists():
        if not ask_yes_no(f"{out_dir} exists. Overwrite?", default=False):
            print("Aborted.")
            return 1
        shutil.rmtree(out_dir)

    out_dir.mkdir(parents=True)

    with (out_dir / "plugin.yaml").open("w", encoding="utf-8") as fp:
        yaml.safe_dump(manifest, fp, sort_keys=False, allow_unicode=True)

    if kind == "python":
        module_dir = out_dir / "src" / entry["module"]
        module_dir.mkdir(parents=True)
        code = PYTHON_STARTERS[starter].replace("__PLUGIN_NAME__", name)
        (module_dir / "__init__.py").write_text(code, encoding="utf-8")

    print(f"\nScaffolded at: {out_dir}")

    # --- optional bundle ---
    if ask_yes_no("\nBuild .lamp bundle now?", default=True):
        bundle_dir = Path("./dist").resolve()
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundle_dir / f"{plugin_id}-{version}.lamp"
        with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in out_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(out_dir))
        print(f"Bundle: {bundle_path}")

    # --- catalog entry ---
    page_yaml_path = TOOLS_DIR / f"{page_name}.yaml"
    if ask_yes_no(f"\nAdd catalog entry to {page_yaml_path}?", default=True):
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        if page_yaml_path.is_file():
            with page_yaml_path.open("r", encoding="utf-8") as fp:
                page_data = yaml.safe_load(fp) or {}
        else:
            page_data = {}

        catalog_entry = {}
        if owner:
            catalog_entry["owner"] = owner
        if about:
            catalog_entry["about"] = about
        if homepage:
            catalog_entry["homepage"] = homepage
        catalog_entry["src_download"] = ""  # fill in once hosted
        if kind == "webview":
            catalog_entry["web_url"] = entry["url"]

        if plugin_id in page_data and not ask_yes_no(
            f"'{plugin_id}' already exists in {page_name}.yaml. Overwrite?",
            default=False,
        ):
            print("  (kept existing entry)")
        else:
            page_data[plugin_id] = catalog_entry
            with page_yaml_path.open("w", encoding="utf-8") as fp:
                yaml.safe_dump(page_data, fp, sort_keys=False, allow_unicode=True)
            print(f"  Updated {page_yaml_path}")

    print("\nDone. Next steps:")
    print(f"  - Fill in src_download in {page_yaml_path} once the .lamp is hosted")
    if kind == "webview":
        print(f"  - Or skip the .lamp entirely: web_url is already set in {page_yaml_path}")
    if is_new_page:
        print(
            f"  - Add a '{page_widget_name(page_name)}' QWidget to the"
            " stackedWidget so the page is reachable"
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
