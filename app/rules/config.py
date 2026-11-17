"""Load and validate config/rules.yaml. Every business number lives there."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# section -> keys that must be present
_REQUIRED = {
    "qualification": [
        "min_net_income", "min_savings", "min_weeks_to_move", "advisor_review_age", "near_miss_pct",
    ],
    "simulation": [
        "savings_to_price", "annual_payment_ratio", "effort_max", "savings_share",
        "price_growth", "years", "round_to",
    ],
    "reply_kinds": ["offer", "ask_info", "decline"],
    "draft": [
        "banned_words", "offer_disclaimer", "max_chars", "max_questions", "ask_priority",
        "hidden_fields", "internal_terms", "offer_facts",
    ],
}
_FIELD_KEYS = ["zona", "plazo", "compradores", "edad", "empleo", "ingresos", "deudas", "net_income", "ahorro"]


class ConfigError(ValueError):
    pass


def load_config(path="config/rules.yaml") -> dict:
    p = Path(path)
    if not p.is_absolute() and not p.exists():
        p = PROJECT_ROOT / p
    if not p.exists():
        raise ConfigError(f"Config file not found: {path}")
    with open(p, encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    validate_config(config, source=str(p))
    return config


def validate_config(config, source="config") -> dict:
    if not isinstance(config, dict):
        raise ConfigError(f"{source}: top level must be a mapping")
    for section, keys in _REQUIRED.items():
        block = config.get(section)
        if not isinstance(block, dict):
            raise ConfigError(f"{source}: missing section '{section}'")
        for key in keys:
            if key not in block:
                raise ConfigError(f"{source}: missing key '{section}.{key}'")
    for section in ("qualification", "simulation"):
        for key, value in config[section].items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigError(f"{source}: '{section}.{key}' must be a number, got {value!r}")
    for key in ("savings_to_price", "annual_payment_ratio", "round_to"):
        if config["simulation"][key] <= 0:
            raise ConfigError(f"{source}: 'simulation.{key}' must be above 0")
    if not 0 <= config["qualification"]["near_miss_pct"] < 1:
        raise ConfigError(f"{source}: 'qualification.near_miss_pct' must be between 0 and 1")
    draft = config["draft"]
    for key in ("max_chars", "max_questions"):
        if isinstance(draft[key], bool) or not isinstance(draft[key], int) or draft[key] < 0:
            raise ConfigError(f"{source}: 'draft.{key}' must be a whole number, got {draft[key]!r}")
    for key in ("banned_words", "ask_priority", "hidden_fields", "internal_terms", "offer_facts"):
        if not isinstance(draft[key], list) or not all(isinstance(x, str) and x for x in draft[key]):
            raise ConfigError(f"{source}: 'draft.{key}' must be a list of strings")
    plain = [k for k in _FIELD_KEYS if k != "net_income"]
    for key in ("ask_priority", "hidden_fields"):
        unknown = [x for x in draft[key] if x not in plain]
        if unknown:
            raise ConfigError(f"{source}: 'draft.{key}' has unknown fields: {', '.join(unknown)}")
    fields = config.get("fields")
    if not isinstance(fields, list) or not all(isinstance(f, dict) and "key" in f and "label" in f for f in fields):
        raise ConfigError(f"{source}: 'fields' must be a list of {{key, label}}")
    keys = [f["key"] for f in fields]
    if keys != _FIELD_KEYS:
        raise ConfigError(f"{source}: 'fields' must be, in order: {', '.join(_FIELD_KEYS)}; got {', '.join(keys)}")
    return config
