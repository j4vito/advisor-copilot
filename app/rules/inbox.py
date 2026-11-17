"""inbox_sort(items). CONTRACTS section 5."""

_FIT_RANK = {"fits": 0, "needs_data": 1, "no_fit": 2}


def inbox_sort(items: list) -> list:
    """Waiting chats (last message from the client) first, then best fit, then longest wait."""
    def key(item):
        return (
            0 if item.get("last_sender") == "cliente" else 1,
            _FIT_RANK.get(item.get("fit"), len(_FIT_RANK)),
            -(item.get("waiting_minutes") or 0),
        )
    return sorted(items, key=key)
