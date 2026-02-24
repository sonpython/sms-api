"""Tests for config.py loading."""
import os
import tempfile
from importlib import reload

import config
from config import _load_config


def test_load_config_parses_key_value():
    c = _load_config()
    assert c["SECRET_KEY"] == "test_secret"
    assert c["ADMIN_KEY"] == "test_admin"


def test_load_config_ignores_comments():
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False)
    tmp.write("# comment line\nKEY=value\n")
    tmp.close()
    old_path = config.CONFIG_PATH
    try:
        config.CONFIG_PATH = tmp.name
        c = config._load_config()
        assert "KEY" in c
        assert c["KEY"] == "value"
    finally:
        config.CONFIG_PATH = old_path
        os.unlink(tmp.name)


def test_load_secret():
    assert config.load_secret() == "test_secret"


def test_load_admin_key():
    assert config.load_admin_key() == "test_admin"
