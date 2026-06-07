from __future__ import annotations

import re

from fastapi.templating import Jinja2Templates

from app.settings import settings


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


def price_input_for_unit(value: object, unit: object = None) -> str:
    formatted = price_input_value(value)
    if not formatted or unit != "rial":
        return formatted
    digits = re.sub(r"\D+", "", formatted)
    if not digits:
        return formatted
    return f"{int(digits) * 10:,}"


def create_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory="app/templates")
    templates.env.filters["price"] = format_price
    templates.env.filters["price_input"] = price_input_value
    templates.env.filters["price_input_for_unit"] = price_input_for_unit
    templates.env.globals["clarity_project_id"] = settings.clarity_project_id.strip()
    return templates
