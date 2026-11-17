"""Rules core: every decision in the product, as pure Python. Values come from config/rules.yaml."""

from .analyze import analyze
from .checks import check_draft
from .config import ConfigError, load_config, validate_config
from .fmt import eur, num
from .inbox import inbox_sort

__all__ = ["analyze", "check_draft", "load_config", "validate_config", "ConfigError", "inbox_sort", "eur", "num"]
