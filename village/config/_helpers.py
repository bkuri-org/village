import os


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


def _parse_int(raw: str | None, default: int) -> int:
    if raw:
        return int(raw)
    return default


def _parse_str(raw: str | None, default: str) -> str:
    if raw:
        return raw
    return default


def _parse_float(raw: str | None, default: float) -> float:
    if raw:
        return float(raw)
    return default


def _env_or_config(env_var: str, config: dict[str, str], *keys: str) -> str | None:
    env_val = os.environ.get(env_var)
    if env_val:
        return env_val
    for key in keys:
        val = config.get(key)
        if val:
            return val
    return None
