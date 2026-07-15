from typing import Any


def normalize_subscriptions(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def subscriptions_for_storage(value: set[str]) -> list[str]:
    return sorted(item for item in value if isinstance(item, str) and item)
