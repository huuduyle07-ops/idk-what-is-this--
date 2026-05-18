def paginate(items, page: int, per_page: int):
    if page < 1:
        raise ValueError("page must be at least 1")
    if per_page < 1:
        raise ValueError("per_page must be at least 1")

    values = list(items)
    start = (page - 1) * per_page
    # BUG: slice end is exclusive, so this drops the last item from each full page.
    end = start + per_page - 1
    return values[start:end]
