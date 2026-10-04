"""Check that every number in an answer comes from the database results.

The model is instructed to compute every figure in SQL and copy it exactly.
This check enforces that mechanically: a number in the answer is supported
only if it equals a value in a query result (allowing for $/%/comma
formatting and the answer's rounding), a value from the question or the SQL
itself, or the row count of a result (e.g. "3 marketplaces").
"""

import re
from decimal import Decimal, InvalidOperation

_NUMBER = re.compile(r"(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?%?")
_LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s+")
_ANY_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _to_decimal(token):
    cleaned = token.replace("$", "").replace(",", "").replace("%", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def numbers_in_answer(text):
    """(token, value) pairs for each number the answer states. Leading list
    numbering ("1. ...") is not a claim and is skipped."""
    text = _LIST_MARKER.sub("", text or "")
    found = []
    for match in _NUMBER.finditer(text):
        value = _to_decimal(match.group(0))
        if value is not None:
            found.append((match.group(0), value))
    return found


def _numbers_in(text):
    values = set()
    for token in _ANY_NUMBER.findall(text or ""):
        try:
            values.add(Decimal(token))
        except InvalidOperation:
            pass
    return values


def supported_values(sources, question=""):
    """Every number the answer may legitimately use."""
    values = _numbers_in(question)
    for source in sources:
        values |= _numbers_in(source.get("sql", ""))
        if "rows" not in source:
            continue
        values.add(Decimal(source["row_count"]))
        for row in source["rows"]:
            for cell in row:
                if cell is None or isinstance(cell, bool):
                    continue
                values |= _numbers_in(str(cell))  # dates and text cells contribute their digits too
    return values


def _matches(value, token, allowed):
    """Exact match, or match after rounding to the answer's precision
    (also as a percentage of a 0–1 ratio)."""
    if value in allowed or -value in allowed:
        return True
    digits = token.replace("%", "").split(".")
    places = len(digits[1]) if len(digits) > 1 else 0
    quantum = Decimal(1).scaleb(-places)
    for candidate in allowed:
        for scaled in (candidate, candidate * 100) if token.endswith("%") else (candidate,):
            try:
                if abs(scaled.quantize(quantum)) == abs(value):
                    return True
            except InvalidOperation:
                continue
    return False


def unsupported_numbers(answer, sources, question=""):
    """Numbers in the answer that no query result supports (empty = verified)."""
    allowed = supported_values(sources, question)
    return [token for token, value in numbers_in_answer(answer) if not _matches(value, token, allowed)]
