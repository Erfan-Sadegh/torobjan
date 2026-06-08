from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re


@dataclass(frozen=True)
class EitaaPhoto:
    file_id: str
    width: int = 0
    height: int = 0


@dataclass
class EitaaProductDraft:
    message_id: str
    product_name: str
    price_toman: str | None
    description: str | None
    message_date: datetime | None
    photos: list[EitaaPhoto] = field(default_factory=list)

    @property
    def best_photo(self) -> EitaaPhoto | None:
        if not self.photos:
            return None
        return sorted(self.photos, key=lambda item: item.width * item.height)[-1]


PRICE_PATTERN = re.compile(
    r"(?:قیمت|فی|مبلغ)\s*[:：]?\s*([۰-۹0-9٠-٩٬,.\s]+)\s*(تومان|تومن|ریال)?",
    re.IGNORECASE,
)
NOISE_LINE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"ثبت\s+سفارش",
        r"ارتباط",
        r"آدرس",
        r"سایت",
        r"پرداخت",
        r"ارسال",
        r"مرجوع",
        r"@",
        r"https?://",
    ]
]
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def extract_eitaa_products(messages: list[dict], max_products: int) -> list[EitaaProductDraft]:
    products: list[EitaaProductDraft] = []
    current: EitaaProductDraft | None = None
    for message in sorted(messages, key=lambda item: int(item.get("message_id") or 0), reverse=True):
        text = _message_text(message)
        photos = _message_photos(message)
        if text and _looks_like_product_text(text):
            product = _product_from_text(message, text)
            if product is None:
                current = None
                continue
            product.photos.extend(photos)
            products.append(product)
            current = product
            if len(products) >= max_products:
                break
            continue
        if photos and current is not None and _photo_is_near_product(message, current):
            current.photos.extend(photos)
    return products


def _message_text(message: dict) -> str | None:
    value = message.get("caption") or message.get("text")
    if not value:
        return None
    text = str(value).strip()
    return text or None


def _message_photos(message: dict) -> list[EitaaPhoto]:
    photos = message.get("photo")
    if not isinstance(photos, list):
        return []
    result: list[EitaaPhoto] = []
    for item in photos:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("file_id") or "").strip()
        if not file_id:
            continue
        result.append(
            EitaaPhoto(
                file_id=file_id,
                width=_to_int(item.get("width")),
                height=_to_int(item.get("height")),
            )
        )
    return result


def _looks_like_product_text(text: str) -> bool:
    return bool(PRICE_PATTERN.search(text))


def _product_from_text(message: dict, text: str) -> EitaaProductDraft | None:
    name = _extract_product_name(text)
    if not name:
        return None
    price = _extract_price_toman(text)
    message_id = str(message.get("message_id") or "").strip()
    return EitaaProductDraft(
        message_id=message_id,
        product_name=name,
        price_toman=price,
        description=text,
        message_date=_to_datetime(message.get("date")),
    )


def _extract_product_name(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        if PRICE_PATTERN.search(line):
            continue
        if any(pattern.search(line) for pattern in NOISE_LINE_PATTERNS):
            continue
        if len(_tokens(line)) < 2 and len(line) < 8:
            continue
        return line[:500]
    return None


def _extract_price_toman(text: str) -> str | None:
    match = PRICE_PATTERN.search(text)
    if not match:
        return None
    digits = _digits(match.group(1))
    if not digits:
        return None
    amount = int(digits)
    unit = str(match.group(2) or "").strip()
    if amount <= 0:
        return None
    if "ریال" in unit:
        amount = amount // 10
    return str(amount) if amount > 0 else None


def _photo_is_near_product(message: dict, product: EitaaProductDraft) -> bool:
    message_id = _to_int(message.get("message_id"))
    product_id = _to_int(product.message_id)
    if product_id and message_id and product_id - message_id > 20:
        return False
    message_date = _to_datetime(message.get("date"))
    if message_date is None or product.message_date is None:
        return True
    return abs((product.message_date - message_date).total_seconds()) <= 60 * 20


def _clean_line(value: str) -> str:
    text = value.strip()
    text = re.sub(r"^[^\wآ-ی۰-۹0-9]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -:؛،")


def _digits(value: object) -> str:
    text = str(value or "").translate(PERSIAN_DIGITS)
    return re.sub(r"\D+", "", text)


def _tokens(value: str) -> list[str]:
    text = value.translate(PERSIAN_DIGITS).lower().replace("\u200c", " ")
    return [token for token in re.split(r"[\s,،؛:()/\\|+\-_.]+", text) if len(token) > 1]


def score_product_match(query: str, candidate_name: str) -> float:
    query_tokens = _meaningful_tokens(query)
    candidate_tokens = _meaningful_tokens(candidate_name)
    if not query_tokens or not candidate_tokens:
        return 0.0
    candidate_token_set = set(candidate_tokens)
    overlap = [token for token in query_tokens if token in candidate_token_set]
    coverage = len(overlap) / len(query_tokens)
    joined_query = " ".join(query_tokens)
    joined_candidate = " ".join(candidate_tokens)
    ratio = SequenceMatcher(None, joined_query, joined_candidate).ratio()
    substring_boost = 0.14 if joined_query and joined_query in joined_candidate else 0.0
    important_boost = 0.10 if len(overlap) >= min(3, len(query_tokens)) else 0.0
    return min(1.0, (coverage * 0.62) + (ratio * 0.28) + substring_boost + important_boost)


def _meaningful_tokens(value: str) -> list[str]:
    stop_words = {
        "کفش",
        "کتونی",
        "اسپرت",
        "زنانه",
        "مردانه",
        "بچگانه",
        "مدل",
        "اصل",
        "درجه",
        "رنگ",
    }
    return [token for token in _tokens(value) if token not in stop_words]


def _to_int(value: object) -> int:
    try:
        return int(str(value or "").translate(PERSIAN_DIGITS))
    except ValueError:
        return 0


def _to_datetime(value: object) -> datetime | None:
    timestamp = _to_int(value)
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
