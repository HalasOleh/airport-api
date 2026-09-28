"""Small, dependency-free guards for payment data sent to the chat."""

import re


# Card numbers contain 13-19 digits and are commonly pasted either without
# separators or with spaces/hyphens. The Luhn check below keeps ordinary long
# identifiers from being rejected just because they contain many digits.
CARD_NUMBER_CANDIDATE = re.compile(
    r"(?<![0-9])(?:[0-9][ -]?){12,18}[0-9](?![0-9])"
)


def _passes_luhn_check(digits: str) -> bool:
    """Return whether a string of digits has a valid payment-card checksum."""
    total = 0
    parity = len(digits) % 2

    for index, character in enumerate(digits):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit

    return total % 10 == 0


def contains_payment_card_number(value: str) -> bool:
    """Detect likely card numbers without retaining or returning their value."""
    for candidate in CARD_NUMBER_CANDIDATE.finditer(value or ""):
        digits = re.sub(r"[^0-9]", "", candidate.group())
        if 13 <= len(digits) <= 19 and _passes_luhn_check(digits):
            return True

    return False
