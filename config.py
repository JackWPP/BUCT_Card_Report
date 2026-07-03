"""Application configuration with local file persistence.

LLM credentials are stored in a user-local JSON file (not environment variables)
so users can configure them through the web UI. The file location follows the
XDG Base Directory spec on Linux/macOS and APPDATA on Windows.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _get_config_dir() -> Path:
    """Return the directory where user config is persisted."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(base) / "BUCT_Card_Report"
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_FILE = _get_config_dir() / "config.json"


# Built-in LLM provider presets shown in the UI.
PROVIDER_PRESETS: list[dict] = [
    {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "hint": "深度求索，国内访问稳定，性价比高",
    },
    {
        "name": "通义千问 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "hint": "阿里云百炼，需先在控制台开通",
    },
    {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "hint": "聚合多种开源模型，注册送额度",
    },
    {
        "name": "智谱 AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "hint": "清华系大模型，提供免费 tier",
    },
    {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "hint": "需科学上网，海外信用卡",
    },
    {
        "name": "自定义",
        "base_url": "",
        "model": "",
        "hint": "兼容 OpenAI 协议的任何服务",
    },
]


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = "deepseek-chat"
    enabled: bool = False

    def is_ready(self) -> bool:
        return self.enabled and bool(self.api_key) and bool(self.base_url)

    def mask_key(self) -> str:
        """Return a masked version of the API key for display."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "*" * len(self.api_key)
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]


@dataclass
class AppConfig:
    """Top-level application config, persisted to disk."""

    # Card system (rarely changed — keep env-overridable for power users)
    card_base_url: str = field(
        default_factory=lambda: os.environ.get(
            "BUCT_CARD_BASE_URL", "https://mcard.buct.edu.cn"
        )
    )
    max_query_days: int = 31

    # LLM (configured via UI, persisted to local file)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # --- Persistence ---
    def save(self) -> None:
        """Persist config to disk (API key written in full — file is local-only)."""
        data = {
            "card_base_url": self.card_base_url,
            "max_query_days": self.max_query_days,
            "llm": asdict(self.llm),
        }
        try:
            CONFIG_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            # Restrict permissions on POSIX: owner read/write only.
            try:
                os.chmod(CONFIG_FILE, 0o600)
            except (OSError, AttributeError):
                pass  # Windows or unsupported FS
            logger.info(f"Config saved to {CONFIG_FILE}")
        except OSError as e:
            logger.error(f"Failed to save config: {e}")
            raise

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from disk; fall back to defaults if missing/corrupt."""
        if not CONFIG_FILE.exists():
            logger.info("No config file found, using defaults")
            return cls()
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to read config file: {e}; using defaults")
            return cls()

        cfg = cls()
        cfg.card_base_url = data.get("card_base_url", cfg.card_base_url)
        cfg.max_query_days = data.get("max_query_days", cfg.max_query_days)
        llm_data = data.get("llm", {}) or {}
        cfg.llm = LLMConfig(
            api_key=llm_data.get("api_key", "") or "",
            base_url=llm_data.get("base_url", "") or "",
            model=llm_data.get("model", "deepseek-chat"),
            enabled=bool(llm_data.get("enabled", False)),
        )

        # Environment variables still win — useful for containers.
        env_key = os.environ.get("LLM_API_KEY")
        env_url = os.environ.get("LLM_BASE_URL")
        env_model = os.environ.get("LLM_MODEL")
        if env_key:
            cfg.llm.api_key = env_key
        if env_url:
            cfg.llm.base_url = env_url
        if env_model:
            cfg.llm.model = env_model
        if env_key and env_url:
            cfg.llm.enabled = True

        return cfg

    def public_view(self) -> dict:
        """Return a JSON-safe view of the config (API key masked)."""
        return {
            "card_base_url": self.card_base_url,
            "llm": {
                "enabled": self.llm.enabled,
                "ready": self.llm.is_ready(),
                "base_url": self.llm.base_url,
                "model": self.llm.model,
                "masked_key": self.llm.mask_key(),
                "has_key": bool(self.llm.api_key),
            },
            "providers": PROVIDER_PRESETS,
            "config_file": str(CONFIG_FILE),
        }


# Module-level singleton (re-loaded on each access so tests can reset it).
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Return the singleton AppConfig, loading it on first call."""
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def reload_config() -> AppConfig:
    """Force-reload config from disk (used after settings update)."""
    global _config
    _config = AppConfig.load()
    return _config