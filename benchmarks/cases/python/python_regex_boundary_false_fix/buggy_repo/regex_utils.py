import re


def count_word(text: str, word: str) -> int:
    """Count occurrences of word as a standalone word in text."""
    # BUG: no word boundaries; matches substrings inside larger words
    pattern = re.escape(word)
    return len(re.findall(pattern, text, re.IGNORECASE))
