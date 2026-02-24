import os

CONFIG_PATH = os.environ.get("PASSKEY_CONF", "passkey.conf")


def _load_config():
    """Load all key=value pairs from passkey.conf into a dict."""
    config = {}
    with open(CONFIG_PATH) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


def load_secret():
    config = _load_config()
    if "SECRET_KEY" not in config:
        raise RuntimeError("SECRET_KEY not found in passkey.conf")
    return config["SECRET_KEY"]


def load_admin_key():
    config = _load_config()
    if "ADMIN_KEY" not in config:
        raise RuntimeError("ADMIN_KEY not found in passkey.conf")
    return config["ADMIN_KEY"]


def load_sms_base_dir():
    config = _load_config()
    return config.get("SMS_BASE_DIR", "/var/spool/sms")
