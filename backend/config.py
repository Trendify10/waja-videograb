import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
CONFIG_EXAMPLE_PATH = Path(__file__).resolve().parent.parent / "config.example.json"

DEFAULTS = {
    "download_folder": "~/Downloads/VideoGrab",
    "default_format": "best",
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        if CONFIG_EXAMPLE_PATH.exists():
            with open(CONFIG_EXAMPLE_PATH) as f:
                data = json.load(f)
        else:
            data = dict(DEFAULTS)
        save_config(data)
        return data
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_download_folder() -> str:
    cfg = load_config()
    folder = os.path.expanduser(cfg.get("download_folder", DEFAULTS["download_folder"]))
    os.makedirs(folder, exist_ok=True)
    return folder
