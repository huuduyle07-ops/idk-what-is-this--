def add_task(title: str, tasks: list[str] = []) -> list[str]:
    # BUG: mutable default list leaks state between calls.
    tasks.append(title)
    return tasks
