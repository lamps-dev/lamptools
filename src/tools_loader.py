import re
from pathlib import Path

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QPushButton,
)

import src.config as config
import src.plugins as plugin


def _page_object_name_to_yaml(object_name: str) -> str:
    # "TextToolsPage" -> "text_tools.yaml"
    name = re.sub(r"Page$", "", object_name)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return f"{snake}.yaml"


def _clear_layout(widget: QWidget) -> None:
    existing = widget.layout()
    if existing is None:
        return
    while existing.count():
        item = existing.takeAt(0)
        child = item.widget()
        if child is not None:
            child.setParent(None)
    QWidget().setLayout(existing)


def _make_tool_card(tool_id: str, fields: dict, page: QWidget) -> QFrame:
    card = QFrame()
    card.setObjectName(f"toolCard_{tool_id}")
    card.setFrameShape(QFrame.Shape.StyledPanel)
    card.setFrameShadow(QFrame.Shadow.Raised)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(4)

    header_row = QHBoxLayout()
    title = QLabel(tool_id)
    title_font = title.font()
    title_font.setPointSize(13)
    title_font.setBold(True)
    title.setFont(title_font)
    header_row.addWidget(title)
    header_row.addStretch(1)

    owner = fields.get("owner")
    if owner:
        suffix = " (verified) ☑️" if owner == "Lamp Studios" else ""
        owner_label = QLabel(f"by {owner}{suffix}")
        owner_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(owner_label)
    layout.addLayout(header_row)

    about = fields.get("about")
    if about:
        about_label = QLabel(str(about))
        about_label.setWordWrap(True)
        layout.addWidget(about_label)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if plugin.check_plugin(tool_id) == "Install":
            open_btn = QPushButton("Install")
            open_btn.clicked.connect(
                lambda _=False, tid=tool_id, u=fields.get("src_download"), p=page:
                    plugin.install_tool(tid, u, p)
            )
        else:
            open_btn = QPushButton("Open")
            open_btn.clicked.connect(
                lambda _=False, tid=tool_id, f=fields, p=page:
                    plugin.open_tool(tid, f, p)
            )
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)
    return card


def _populate_with_message(page: QWidget, message: str) -> None:
    _clear_layout(page)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(12, 12, 12, 12)
    label = QLabel(message)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setWordWrap(True)
    layout.addWidget(label)


def load_tools_for_page(page: QWidget) -> None:
    yaml_name = _page_object_name_to_yaml(page.objectName())
    yaml_path = Path(config.tools_dir) / yaml_name

    if not yaml_path.is_file():
        _populate_with_message(page, f"No tools file found: {yaml_name}")
        return

    try:
        with yaml_path.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
    except yaml.YAMLError as exc:
        _populate_with_message(page, f"Failed to parse {yaml_name}:\n{exc}")
        return

    if not isinstance(data, dict) or not data:
        _populate_with_message(page, f"{yaml_name} contains no tools.")
        return

    _clear_layout(page)
    outer = QVBoxLayout(page)
    outer.setContentsMargins(12, 12, 12, 12)
    outer.setSpacing(0)

    scroll = QScrollArea(page)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    outer.addWidget(scroll)

    container = QWidget()
    container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    inner = QVBoxLayout(container)
    inner.setContentsMargins(4, 4, 4, 4)
    inner.setSpacing(10)

    for tool_id, fields in data.items():
        inner.addWidget(_make_tool_card(str(tool_id), fields or {}, page))

    inner.addStretch(1)
    scroll.setWidget(container)


def load_all_tool_pages(stacked_widget) -> None:
    tools_dir = Path(config.tools_dir)
    if not tools_dir.is_dir():
        return
    for i in range(stacked_widget.count()):
        page = stacked_widget.widget(i)
        object_name = page.objectName()
        if "tools" not in object_name.lower():
            continue
        yaml_name = _page_object_name_to_yaml(object_name)
        if (tools_dir / yaml_name).is_file():
            load_tools_for_page(page)
