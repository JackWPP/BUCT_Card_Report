"""Tests for the LLM configuration module."""
import json
from pathlib import Path
import pytest

import config as cfg_module
from config import LLMConfig, AppConfig, PROVIDER_PRESETS, get_config, reload_config


@pytest.fixture(autouse=True)
def reset_module_config():
    """Force a fresh config load between tests so they don't leak state."""
    cfg_module._config = None
    yield
    cfg_module._config = None


def test_default_config_is_not_ready():
    cfg = AppConfig()
    assert not cfg.llm.is_ready()
    assert cfg.llm.api_key == ""
    assert cfg.llm.base_url == ""


def test_llm_config_is_ready():
    llm = LLMConfig(api_key="sk-x", base_url="https://x", model="m", enabled=True)
    assert llm.is_ready()


def test_llm_config_disabled_means_not_ready():
    llm = LLMConfig(api_key="sk-x", base_url="https://x", model="m", enabled=False)
    assert not llm.is_ready()


def test_mask_key_short():
    llm = LLMConfig(api_key="abcd")
    assert llm.mask_key() == "****"


def test_mask_key_long():
    llm = LLMConfig(api_key="sk-1234567890abcdef")
    masked = llm.mask_key()
    assert masked.startswith("sk-1")
    assert masked.endswith("cdef")
    assert "*" in masked
    assert "234567890abcde" not in masked


def test_mask_key_empty():
    assert LLMConfig().mask_key() == ""


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    # Redirect config file to a temp path
    fake_file = tmp_path / "config.json"
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", fake_file)

    cfg = AppConfig()
    cfg.llm.api_key = "sk-test-12345678"
    cfg.llm.base_url = "https://api.test/v1"
    cfg.llm.model = "test-model"
    cfg.llm.enabled = True
    cfg.save()

    assert fake_file.exists()
    cfg_module._config = None
    loaded = AppConfig.load()
    assert loaded.llm.api_key == "sk-test-12345678"
    assert loaded.llm.base_url == "https://api.test/v1"
    assert loaded.llm.model == "test-model"
    assert loaded.llm.enabled is True


def test_load_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", tmp_path / "missing.json")
    cfg = AppConfig.load()
    assert cfg.llm.api_key == ""
    assert cfg.card_base_url == "https://mcard.buct.edu.cn"


def test_load_corrupt_file_returns_defaults(tmp_path, monkeypatch):
    bad = tmp_path / "config.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", bad)
    cfg = AppConfig.load()
    assert cfg.llm.api_key == ""


def test_env_vars_override_disk(tmp_path, monkeypatch):
    disk_cfg = tmp_path / "config.json"
    disk_cfg.write_text(json.dumps({
        "llm": {"api_key": "from-disk", "base_url": "https://disk/v1", "enabled": True}
    }), encoding="utf-8")
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", disk_cfg)
    monkeypatch.setenv("LLM_API_KEY", "from-env")
    monkeypatch.setenv("LLM_BASE_URL", "https://env/v1")

    cfg = AppConfig.load()
    # Env should win for power users / containers
    assert cfg.llm.api_key == "from-env"
    assert cfg.llm.base_url == "https://env/v1"


def test_public_view_masks_api_key():
    cfg = AppConfig()
    cfg.llm.api_key = "sk-1234567890abcdef"
    cfg.llm.base_url = "https://api.test/v1"
    cfg.llm.enabled = True
    view = cfg.public_view()
    assert view["llm"]["has_key"] is True
    assert view["llm"]["masked_key"] != cfg.llm.api_key
    assert "cdef" in view["llm"]["masked_key"]
    # Full key must never leak into the public view
    assert cfg.llm.api_key not in view["llm"]["masked_key"]
    assert len(PROVIDER_PRESETS) >= 3


def test_provider_presets_have_required_fields():
    for p in PROVIDER_PRESETS:
        assert "name" in p
        assert "base_url" in p
        assert "model" in p
        assert "hint" in p


def test_reload_config_resets_singleton(tmp_path, monkeypatch):
    fake = tmp_path / "config.json"
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", fake)
    cfg = get_config()
    assert cfg.llm.api_key == ""

    fake.write_text(json.dumps({"llm": {"api_key": "x", "base_url": "y", "enabled": True}}),
                    encoding="utf-8")
    cfg2 = reload_config()
    assert cfg2.llm.api_key == "x"
    # get_config now returns the reloaded instance
    assert get_config() is cfg2