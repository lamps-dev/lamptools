import os
import pathlib
import subprocess
import sys
import src.config as config
import platform

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"


def show_startup_error(message, title):
    """Modal warning for problems found before Qt exists.

    The Tk root is destroyed once the user clicks OK — without that it stays
    alive as a hidden window and the process never fully lets go of it.
    """
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror(message=message, title=title, parent=root)
    finally:
        root.destroy()


def linux_session_warning():
    """Warning text tailored to the display server / desktop we're running on."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()
    on_wayland = session == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))
    on_plasma = "KDE" in desktop or "PLASMA" in desktop

    base = "You are running this app on Linux, some features may sometimes not work yet."

    if on_wayland and on_plasma:
        return base + (
            "\n\nDetected KDE Plasma on Wayland. Window positioning, the splash "
            "overlay and always-on-top behaviour are handled by the compositor "
            "here, so they may not act the way they do on Windows. If the window "
            "misbehaves, relaunch with QT_QPA_PLATFORM=xcb to use XWayland."
        )
    if on_wayland:
        return base + (
            "\n\nDetected a Wayland session. Window positioning and the splash "
            "overlay are controlled by the compositor and may not behave the way "
            "they do on Windows. If the window misbehaves, relaunch with "
            "QT_QPA_PLATFORM=xcb to use XWayland."
        )
    if on_plasma:
        return base + "\n\nDetected KDE Plasma on X11."
    return base


if IS_WINDOWS:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Lamp Studios\Lamp Tools\Checks")
        val, _ = winreg.QueryValueEx(key, "IsUsing10andabove")
    except Exception as e:
        show_startup_error(
            "You are below the required version of Windows! Please run this on Windows 10 1507 and above.\nExit code: -1.",
            str(e),
        )
        #sys.exit(-1)

if IS_LINUX:
    show_startup_error(linux_session_warning(), "WARNING!")

from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QMainWindow, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QPauseAnimation, QSequentialAnimationGroup, Qt, QTimer, QPropertyAnimation
from src.ui.ui import Ui_MainWindow
from src.ui.buttons import *
from src.tools_loader import load_all_tool_pages


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(f"LampTools GUI - {config.ver}")
        
        # sidebar buttons
        self.ui.pushButton.clicked.connect(lambda: go_to_page(self, 0))    # Home
        self.ui.pushButton_2.clicked.connect(lambda: go_to_page(self, 1))  # Settings
        self.ui.pushButton_4.clicked.connect(lambda: go_to_page(self, 2))  # About
        self.ui.pushButton_5.clicked.connect(lambda: go_to_page(self, 3))  # Text Tools
        
        # menu actions
        self.ui.actionSettings.triggered.connect(lambda: go_to_page(self, 1))
        self.ui.actionExit.triggered.connect(lambda: close_window(self))
        self.ui.actionSilly_33.triggered.connect(self.do_silly)

        # populate tool pages from src/tools/<page>.yaml
        load_all_tool_pages(self.ui.stackedWidget)
    

    def show_overlay_fade(self, image_path, hold_ms=1000):
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            print(f"❌ failed to load: {image_path}")
            return
        
        overlay = QLabel(self)
        overlay.setPixmap(pixmap)
        overlay.setAlignment(Qt.AlignCenter)
        overlay.setGeometry(0, 0, self.width(), self.height())
        
        effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        
        overlay.show()
        overlay.raise_()
        
        # fade in
        fade_in = QPropertyAnimation(effect, b"opacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        
        # hold (pause)
        pause = QPauseAnimation(hold_ms)
        
        # fade out
        fade_out = QPropertyAnimation(effect, b"opacity")
        fade_out.setDuration(3000)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        
        # chain them in sequence
        self.overlay_anim = QSequentialAnimationGroup(self)
        self.overlay_anim.addAnimation(fade_in)
        self.overlay_anim.addAnimation(pause)
        self.overlay_anim.addAnimation(fade_out)
        self.overlay_anim.finished.connect(overlay.deleteLater)
        self.overlay_anim.start()
    
    def do_silly(self):
        import os
        image_path = "src/test.webp"
        abs_path = os.path.abspath(image_path)
        print(f"looking for image at: {abs_path}")
        print(f"file exists: {os.path.exists(abs_path)}")
            
        do_silly_sound()
        self.show_overlay_fade(image_path, hold_ms=1000)


app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
