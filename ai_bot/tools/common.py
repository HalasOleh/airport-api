"""Helpers shared by the tool modules.

Every value that reaches these functions was produced by a language model, so
nothing here trusts its input: a limit can be a string, a date can be prose, a
city name can be in any case. They coerce or give up, but never raise.
"""
import logging
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


def clamp_limit(limit, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    """Bound a row count the model chose for us.

    The model fills `limit` in itself and is free to ask for 10000 rows, so the
    ceiling has to live here rather than in the schema description.
    """
    try:
        return max(1, min(int(limit), maximum))
    except (TypeError, ValueError):
        return default


def money(cents) -> dict:
    """Cents to both the raw number and a formatted string.

    Handing the model a ready-made "$120.00" keeps it from doing the division
    itself - small models are unreliable at arithmetic, and this is money.
    Decimal, not float, for the same reason Flight.base_price is an integer.
    """
    try:
        cents = int(cents)
    except (TypeError, ValueError):
        cents = 0
    dollars = (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))
    return {"amount_cents": cents, "amount": f"${dollars:,.2f}"}


def day_range(date_str):
    """"2026-08-26" to the timezone-aware [start, end) of that calendar day.

    Returns None for anything unparseable; callers turn that into an error dict
    so the model can correct itself instead of the connection dying.
    """
    try:
        day = datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

    try:
        start = timezone.make_aware(datetime.combine(day, time.min))
    except Exception:
        # Midnight does not exist on some DST transitions in some zones.
        logger.warning("Could not localise midnight for %s", day)
        return None

    return start, start + timedelta(days=1)


def airport_q(token: str, field: str) -> Q:
    """Match one token against an airport as either its code or its city.

    The model is told it may pass either, because a user writing "Київ" should
    not have to know that the code is KBP. Note there is no .upper() here: the
    previous version uppercased the token before comparing, which turned a city
    name into "КИЇВ" and could never match. `iexact` already ignores case.
    """
    token = str(token).strip()
    return Q(**{f"{field}__code__iexact": token}) | Q(
        **{f"{field}__city__name__icontains": token}
    )
