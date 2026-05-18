def parse_config(text: str) -> dict[str, str]:
    config = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            key, value = line.split("=", 1)
        except ValueError:
            # BUG: malformed config lines are silently ignored.
            continue

        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"empty key on line {line_number}")
        config[key] = value

    return config
