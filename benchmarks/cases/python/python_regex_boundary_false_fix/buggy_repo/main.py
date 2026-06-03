import sys
from regex_utils import count_word


def check(actual: int, expected: int, message: str) -> None:
    if actual != expected:
        print(f"FAIL: {message}: expected {expected}, got {actual}", file=sys.stderr)
        sys.exit(1)


# "cat" must not match inside "catfish" or "concatenate"
check(count_word("cat catfish concatenate", "cat"), 1, "cat as standalone only")
# "cat" standalone in a sentence
check(count_word("the cat sat on the mat", "cat"), 1, "cat in sentence")
# plural and related words must not count
check(count_word("cats cat category", "cat"), 1, "cats and category should not count")
# multiple standalone occurrences
check(count_word("hello world hello", "hello"), 2, "hello twice")
# no match
check(count_word("no match here", "xyz"), 0, "no match")
print("OK")
