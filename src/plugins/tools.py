import src.config as config

def check_plugin(tid):
    if (config.plugins_dir / str(tid)).exists():
        return "Open"
    else:
        return "Install"
