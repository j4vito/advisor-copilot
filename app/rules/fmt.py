"""Spanish number formatting, used for every `display` and fact."""

from decimal import Decimal, ROUND_HALF_UP


def to_int(value) -> int:
    """Round half up to an int, without float surprises."""
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def num(value) -> str:
    """3800 -> '3.800'. Whole numbers only, dot as thousands separator."""
    n = to_int(value)
    sign = "-" if n < 0 else ""
    return sign + f"{abs(n):,}".replace(",", ".")


def eur(value) -> str:
    """3800 -> '3.800 €'."""
    return f"{num(value)} €"


def num_range(lo, hi) -> str:
    """One number when both ends match, 'a .. b' otherwise."""
    if to_int(lo) == to_int(hi):
        return num(lo)
    return f"{num(lo)} a {num(hi)}"


def join_es(items) -> str:
    """['a', 'b', 'c'] -> 'a, b y c'."""
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def capitalize(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text
