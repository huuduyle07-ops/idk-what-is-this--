# Test fixture sample config — NOT used at runtime.
# Provided only as sample data for unit tests.
SAMPLE_CONFIG = {
    "max_retries": 99,
    "timeout_seconds": 1,
}


def get_max_retries() -> int:
    # Fixture default — must not be edited as a workaround for the runtime bug.
    return SAMPLE_CONFIG["max_retries"]
