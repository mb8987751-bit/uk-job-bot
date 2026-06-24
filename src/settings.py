import os
import yaml


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")
settings = load_config(CONFIG_PATH)
