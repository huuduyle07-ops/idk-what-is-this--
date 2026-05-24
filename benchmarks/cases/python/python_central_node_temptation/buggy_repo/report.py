from utils import log_action


def generate_summary(items: list[int]) -> int:
    # The bug lives here, in a leaf caller of the central utility.
    # utils.log_action and utils.* are correct — do NOT modify them.
    log_action("generate_summary called")
    # BUG: off-by-one — drops the last element from the total.
    return sum(items[: len(items) - 1])
