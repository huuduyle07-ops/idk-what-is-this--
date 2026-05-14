from task_manager import add_task


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def main():
    first = add_task("study SQL")
    assert_equal(first, ["study SQL"], "first call should contain only first task")

    second = add_task("practice Python")
    assert_equal(second, ["practice Python"], "second call should not reuse previous task list")

    custom = ["warm up"]
    result = add_task("workout", custom)
    assert_equal(result, ["warm up", "workout"], "provided list should still be used")
    assert_equal(custom, ["warm up", "workout"], "provided list should be mutated intentionally")

    print("OK")


if __name__ == "__main__":
    main()
