def validate_age(age) -> bool:
    """Return True if age is a valid positive integer."""
    # BUG: accepts zero — age must be strictly greater than zero
    return isinstance(age, int) and age >= 0
