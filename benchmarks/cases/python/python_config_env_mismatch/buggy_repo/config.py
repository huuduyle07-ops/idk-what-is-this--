import os


def get_database_url() -> str:
    # BUG: reads DB_CONNECTION_STRING but the environment uses DATABASE_URL
    url = os.environ.get("DB_CONNECTION_STRING", "")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url


def get_port() -> int:
    raw = os.environ.get("SERVER_PORT", "8080")
    return int(raw)
