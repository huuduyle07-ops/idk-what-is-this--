from report import generate_summary
from tracker import track_event


def assert_equal(actual, expected, message):
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def main():
    # track_event uses utils.log_action heavily — exercising the central util.
    track_event("login")
    track_event("checkout")
    track_event("logout")

    # report.generate_summary is where the math defect actually lives.
    assert_equal(
        generate_summary([10, 20, 30]),
        60,
        "generate_summary([10, 20, 30]) should be 60",
    )
    assert_equal(
        generate_summary([7]),
        7,
        "generate_summary([7]) should be 7",
    )
    assert_equal(
        generate_summary([]),
        0,
        "generate_summary([]) should be 0",
    )
    print("OK")


if __name__ == "__main__":
    main()
