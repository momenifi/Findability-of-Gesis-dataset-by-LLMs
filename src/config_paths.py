from pathlib import Path


def resolve_output_dir(cfg: dict) -> Path:
    variants = [str(value).strip() for value in cfg.get("query_variants", []) if str(value).strip()]
    output_dirs = cfg.get("output_dir_by_variant", {}) or {}

    if len(variants) == 1 and variants[0] in output_dirs:
        return Path(output_dirs[variants[0]])

    return Path(cfg.get("output_dir", "."))


__all__ = ["resolve_output_dir"]
