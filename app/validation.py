from collections.abc import Callable
from typing import TypeVar


Number = TypeVar("Number", int, float)


def parse_required_number(value: str, label: str, parser: Callable[[str], Number]) -> Number:
    if not value.strip():
        raise ValueError(f"{label} is required.")
    try:
        return parser(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a valid number.") from error
