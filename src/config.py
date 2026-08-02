r"""
 ___       ________  _____ ______   ________        _________  ________  ________  ___       ________      
|\  \     |\   __  \|\   _ \  _   \|\   __  \      |\___   ___\\   __  \|\   __  \|\  \     |\   ____\     
\ \  \    \ \  \|\  \ \  \\\__\ \  \ \  \|\  \     \|___ \  \_\ \  \|\  \ \  \|\  \ \  \    \ \  \___|_    
 \ \  \    \ \   __  \ \  \\|__| \  \ \   ____\         \ \  \ \ \  \\\  \ \  \\\  \ \  \    \ \_____  \   
  \ \  \____\ \  \ \  \ \  \    \ \  \ \  \___|          \ \  \ \ \  \\\  \ \  \\\  \ \  \____\|____|\  \  
   \ \_______\ \__\ \__\ \__\    \ \__\ \__\              \ \__\ \ \_______\ \_______\ \_______\____\_\  \ 
    \|_______|\|__|\|__|\|__|     \|__|\|__|               \|__|  \|_______|\|_______|\|_______|\_________\
                                                                                               \|_________|                                                                                                                                                                           
"""

import os
import pathlib
import sys

ver = version = "v1.0"
tools = "tools/"
tools_dir = (pathlib.Path(__file__).resolve().parent / tools).resolve()


def _user_data_dir():
    """Per-user writable app data dir, following each platform's convention."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or (pathlib.Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (pathlib.Path.home() / ".local" / "share")
    return pathlib.Path(base) / "LampTools"


plugins_dir = _user_data_dir() / "plugins"