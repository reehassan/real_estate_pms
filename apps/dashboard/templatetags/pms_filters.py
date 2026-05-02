from django import template

register = template.Library()


@register.filter
def pkr(value):
    """
    Formats a number in Pakistani Rupee format.
    e.g. 1250000 → PKR 12,50,000
    Uses the South Asian numbering system (lakh/crore grouping).
    """
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 'PKR 0'

    if value == 0:
        return 'PKR 0'

    negative = value < 0
    value = abs(value)

    s = str(value)

    # South Asian grouping: last 3 digits, then groups of 2
    if len(s) <= 3:
        formatted = s
    else:
        # rightmost 3 digits
        last3 = s[-3:]
        rest = s[:-3]
        # now group rest in chunks of 2 from the right
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        parts.reverse()
        formatted = ','.join(parts) + ',' + last3

    return ('PKR -' if negative else 'PKR ') + formatted


@register.filter
def pkr_short(value):
    """
    Compact format for large numbers in stat cards.
    e.g. 1250000 → PKR 12.5L  |  15000000 → PKR 1.5Cr
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 'PKR 0'

    if value >= 10_000_000:
        return f'PKR {value / 10_000_000:.1f}Cr'
    elif value >= 100_000:
        return f'PKR {value / 100_000:.1f}L'
    else:
        return f'PKR {int(value):,}'