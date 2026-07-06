_LIST_KEYS = {"regulatory_scope"}
_KNOWN_KEYS = {
    "app_name",
    "language",
    "framework",
    "regulatory_scope",
    "data_classification",
    "risk_tier",
    "team_owner",
    "security_contact",
}

def _clean(value: str) -> str:
    return value.strip().strip('"').strip("'")

def parse_context_file(raw: str) -> dict:
    result: dict = {}
    last_list_key: str | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped in ("---", "```", "```yaml", "```yml") or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and last_list_key:
            result.setdefault(last_list_key, []).append(_clean(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip().lower().replace(" ", "_")
        value = value.strip()
        if key not in _KNOWN_KEYS:
            last_list_key = None
            continue
        if key in _LIST_KEYS:
            last_list_key = key
            if value.startswith("[") and value.endswith("]"):
                items = [_clean(v) for v in value[1:-1].split(",") if _clean(v)]
                result[key] = items
            elif value:
                result[key] = [_clean(value)]
            else:
                result.setdefault(key, [])
        else:
            last_list_key = None
            if value:
                result[key] = _clean(value)
    return result
