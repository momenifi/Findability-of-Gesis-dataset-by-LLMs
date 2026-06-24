from pathlib import Path

VARIANT_ALIASES = {
    "V1": "V1_TOPIC_COUNTRY_TIME_ALL_TOPICS",
    "V2": "V2_TOPIC_COUNTRY_TIME_SINGLE_TOPIC",
    "V3": "V3_TITLE_ONLY",
    "V4": "V4_TOPIC_COUNTRY_TIME_UNIVERSE_ANALYSIS_UNIT_ALL_TOPICS",
    "V5": "V5_TOPIC_COUNTRY_TIME_UNIVERSE_ALL_TOPICS",
}


def resolve_variant(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in VARIANT_ALIASES:
        return VARIANT_ALIASES[normalized]

    for full_name in VARIANT_ALIASES.values():
        if normalized == full_name.upper():
            return full_name

    aliases = ", ".join(VARIANT_ALIASES)
    raise ValueError(f"Unknown query variant '{value}'. Use one of: {aliases}, or a full variant name.")


def apply_variant_override(cfg: dict, variant: str | None) -> dict:
    if not variant:
        return cfg
    updated = dict(cfg)
    updated["query_variants"] = [resolve_variant(variant)]
    return updated


def resolve_output_dir(cfg: dict) -> Path:
    variants = [str(value).strip() for value in cfg.get("query_variants", []) if str(value).strip()]
    output_dirs = cfg.get("output_dir_by_variant", {}) or {}

    if len(variants) == 1 and variants[0] in output_dirs:
        return Path(output_dirs[variants[0]])

    return Path(cfg.get("output_dir", "."))


__all__ = ["VARIANT_ALIASES", "apply_variant_override", "resolve_output_dir", "resolve_variant"]
