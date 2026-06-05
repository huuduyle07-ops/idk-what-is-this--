import sys

from windowing import visible_item_ids


ITEMS = [
    {"id": "A"},
    {"id": "B"},
    {"id": "C"},
    {"id": "D"},
    {"id": "E"},
]


def assert_equal(actual, expected, message):
    if actual != expected:
        print(
            f"FAIL: {message}: expected {expected!r}, got {actual!r}",
            file=sys.stderr,
        )
        sys.exit(1)


assert_equal(visible_item_ids(ITEMS, 0, 2), ["A", "B"], "first page has two items")
assert_equal(visible_item_ids(ITEMS, 1, 2), ["C", "D"], "second page has two items")
assert_equal(visible_item_ids(ITEMS, 2, 2), ["E"], "last partial page has one item")

print("OK")
