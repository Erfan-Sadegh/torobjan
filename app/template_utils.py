from __future__ import annotations

import re

from fastapi.templating import Jinja2Templates


def format_price(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    normalized = text.replace(",", "")
    digits = re.sub(r"\D+", "", normalized)
    if not digits:
        return text
    return f"{int(digits):,}"


def price_input_value(value: object) -> str:
    formatted = format_price(value)
    if formatted in {"", "0"}:
        return ""
    return formatted


def create_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory="app/templates")
    templates.env.filters["price"] = format_price
    templates.env.filters["price_input"] = price_input_value
    return templates
