def visible_item_ids(items, page, page_size):
    start = page * page_size
    end = start + page_size
    return [
        item["id"]
        for index, item in enumerate(items)
        if start <= index <= end
    ]
