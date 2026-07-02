from dataclasses import dataclass, field
from typing import Optional
import os

@dataclass
class Config:
    # Card system
    card_base_url: str = "https://mcard.buct.edu.cn"
    max_query_days: int = 31

    # LLM (optional)
    llm_api_key: Optional[str] = field(default_factory=lambda: os.environ.get("LLM_API_KEY"))
    llm_base_url: Optional[str] = field(default_factory=lambda: os.environ.get("LLM_BASE_URL"))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "deepseek-chat"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url)
