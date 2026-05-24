from checkout import process_order


def main():
    total = process_order([10.0, 20.0, 30.0])
    if total != 60.0:
        raise AssertionError(
            f"process_order([10, 20, 30]) should be 60.0, got {total}"
        )

    total_single = process_order([5.0])
    if total_single != 5.0:
        raise AssertionError(
            f"process_order([5]) should be 5.0, got {total_single}"
        )

    total_empty = process_order([])
    if total_empty != 0.0:
        raise AssertionError(
            f"process_order([]) should be 0.0, got {total_empty}"
        )

    print("OK")


if __name__ == "__main__":
    main()
