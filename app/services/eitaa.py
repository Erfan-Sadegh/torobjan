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
        r"ساعت\s+کاری",
        r"سایت",
        r"پرداخت",
        r"ارسال",
        r"مرجوع",
        r"فروشگاه\s+کوثر",
        r"فروش\s+ویژ",
        r"کالابرگ",
        r"فعال",
        r"لیست\s+تره",
        r"محصولات\s+پروتئینی",
        r"سبزیجات",
        r"سیفی",
        r"میوه",
        r"شماره\s+تماس",
        r"وزن\s+محصول",
        r"وزن\s+جعبه",
        r"سبد\s+کالا",
        r"مشاهده\s+موقعیت",
        r"موقعیت\s+در\s+نقشه",
        r"به\s+ازای",
        r"تاریخ\s+روز",
        r"درشت\s+بار",
        r"سالم",
        r"یکدست",
        r"ارزان",
        r"فوق\s+العاده",
        r"کیفیت",
        r"در\s+دو\s+نوع",
        r"^در\s+سایز",
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
        if text:
            extracted = _products_from_text(message, text, allow_missing_price=bool(photos))
            if not extracted:
                current = None
            else:
                if len(extracted) == 1:
                    extracted[0].photos.extend(photos)
                    current = extracted[0]
                else:
                    current = None
                remaining = max_products - len(products)
                products.extend(extracted[:remaining])
                if len(products) >= max_products:
                    break
                continue
        if not text and photos and current is not None and _photo_is_near_product(message, current):
            current.photos.extend(photos)
            if len(products) >= max_products:
                break
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
    return bool(_extract_product_entries(text))


def _products_from_text(message: dict, text: str, allow_missing_price: bool = False) -> list[EitaaProductDraft]:
    entries = _extract_product_entries(text, allow_missing_price=allow_missing_price)
    message_id = str(message.get("message_id") or "").strip()
    products: list[EitaaProductDraft] = []
    for index, (name, price) in enumerate(entries, start=1):
        products.append(
            EitaaProductDraft(
                message_id=message_id if len(entries) == 1 else f"{message_id}:{index}",
                product_name=name,
                price_toman=price,
                description=text,
                message_date=_to_datetime(message.get("date")),
            )
        )
    return products


def _extract_product_entries(text: str, allow_missing_price: bool = False) -> list[tuple[str, str | None]]:
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    entries: list[tuple[str, str | None]] = []
    current_name: str | None = None
    for line in lines:
        if _is_noise_line(line):
            continue
        direct = _direct_line_entry(line)
        if direct is not None:
            name, price = direct
            if current_name and _is_packaging_detail_name(name):
                name = f"{current_name} {name}"
            entries.append((name, price))
            current_name = None
            continue
        price = _context_price(line)
        if price and current_name:
            entries.append((current_name, price))
            current_name = None
            continue
        if _looks_like_name_line(line):
            current_name = line[:500]
    if not entries:
        name = _extract_product_name(text)
        price = _extract_price_toman(text)
        if name and (price or allow_missing_price and _looks_like_missing_price_product(name, text)):
            entries.append((name, price))
    return _dedupe_entries(entries)


def _direct_line_entry(line: str) -> tuple[str, str | None] | None:
    normalized = _normalize_text(line)
    patterns = [
        r"^(?P<name>.+?)\s*(?:[:：]|—|ـ{2,}|--+|-|_)\s*(?P<price>[۰-۹0-9٠-٩][۰-۹0-9٠-٩٬,./\s]*)\s*(?:تومان|تومن|ریال)?\s*$",
        r"^(?P<name>.+?)\s+(?:کیلویی|کیلو)\s*(?P<price>[۰-۹0-9٠-٩][۰-۹0-9٠-٩٬,./\s]*)\s*(?:تومان|تومن|ریال)?\s*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        name = _clean_product_name(match.group("name"))
        price = _price_fragment_to_toman(match.group("price"), normalized)
        if name and price:
            return name, price
    return None


def _is_packaging_detail_name(name: str) -> bool:
    tokens = _tokens(name)
    if not tokens:
        return False
    packaging_tokens = {"شانه", "بسته", "جعبه", "عدد", "عددی", "کارتن", "دانه", "کیلویی", "کیلو", "گرمی", "گرم"}
    return set(tokens).issubset(packaging_tokens) or tokens[0] in {"شانه", "بسته", "جعبه", "کارتن"}


def _context_price(line: str) -> str | None:
    normalized = _normalize_text(line)
    if "قیمت بازار" in normalized:
        return None
    if any(keyword in normalized for keyword in ["قیمت کوثر", "قیمت محصول", "قیمت هر", "قیمت هرجعبه"]):
        return _price_fragment_to_toman(normalized, normalized)
    return None


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
        return _clean_product_name(line)
    return None


def _extract_price_toman(text: str) -> str | None:
    match = PRICE_PATTERN.search(text)
    if not match:
        return None
    return _price_fragment_to_toman(match.group(1), match.group(0))


def _price_fragment_to_toman(value: object, context: str) -> str | None:
    digits = _digits(value)
    if not digits:
        return None
    amount = int(digits)
    unit = str(context or "").strip()
    if amount <= 0:
        return None
    if "ریال" in unit:
        amount = amount // 10
    elif amount < 10000:
        amount *= 1000
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


def _normalize_text(value: str) -> str:
    text = value.replace("\u200c", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_product_name(value: str) -> str | None:
    text = _clean_line(value)
    text = re.sub(r"^نام\s+محصول\s*:?\s*#?", "", text, flags=re.IGNORECASE)
    text = text.replace("#", "").replace("_", " ")
    text = re.sub(r"\b(?:کیلو|کیلویی|قیمت|محصول)\b", "", text).strip(" -:؛،")
    text = re.sub(r"\s+", " ", text)
    if not text or _is_noise_line(text):
        return None
    if len(_tokens(text)) < 1:
        return None
    return text[:500]


def _is_noise_line(line: str) -> bool:
    return any(pattern.search(line) for pattern in NOISE_LINE_PATTERNS)


def _looks_like_name_line(line: str) -> bool:
    if _is_noise_line(line):
        return False
    if PRICE_PATTERN.search(line):
        return False
    if _context_price(line):
        return False
    if _looks_like_price_detail_line(line):
        return False
    if len(_tokens(line)) < 2 and len(line) < 8:
        return False
    return True


def _looks_like_price_detail_line(line: str) -> bool:
    normalized = _normalize_text(line)
    if not _digits(normalized):
        return False
    return bool(
        re.search(r"(?:کیلویی|کیلو|شانه|جعبه|بسته|گرم|عدد)", normalized)
        and re.search(r"(?:تومان|تومن|ریال|[۰-۹0-9٠-٩])", normalized)
    )


def _looks_like_missing_price_product(name: str, text: str) -> bool:
    tokens = _tokens(name)
    if len(tokens) < 2 or len(tokens) > 10:
        return False
    normalized_name = _normalize_text(name)
    reject_patterns = [
        r"قم|پردیسان|بلوار|خیابان|میدان|کوچه|آدرس",
        r"ساعت\s+کاری|امروز|فردا|جمعه|شنبه|یکشنبه|دوشنبه|سه\s*شنبه|چهارشنبه|پنجشنبه",
        r"ایام|امام|الله|علی|عید|شهادت|تسلیت|مبارک|ماه\s+محرم|ماه\s+رمضان",
        r"فروشگاه|آنتیک\s+جهان|ثبت\s+سفارش|شماره\s+تماس|دسته\s*بندی|»",
    ]
    if any(re.search(pattern, normalized_name) for pattern in reject_patterns):
        return False
    generic_tokens = {
        "بسیار",
        "خوش",
        "رخ",
        "باهیب",
        "باهیبت",
        "باهبت",
        "ایتالیایی",
        "مارک",
        "دار",
        "فعال",
        "کمیاب",
        "زیبا",
        "تمیز",
        "سالم",
    }
    if len(tokens) <= 4 and set(tokens).issubset(generic_tokens):
        return False
    return True


def _dedupe_entries(entries: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    deduped: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for name, price in entries:
        key = (name, price)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((name, price))
    return deduped


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
    candidate_only_blockers = {"بذر", "نهال", "دستگاه", "کتاب", "جزوه", "آموزش", "دانلود", "موتور"}
    blocker_overlap = candidate_only_blockers.intersection(candidate_tokens) - set(query_tokens)
    if blocker_overlap:
        return 0.0
    if "خشک" in candidate_tokens and "خشک" not in query_tokens:
        return 0.0
    candidate_token_set = set(candidate_tokens)
    overlap = [token for token in query_tokens if token in candidate_token_set]
    coverage = len(overlap) / len(query_tokens)
    joined_query = " ".join(query_tokens)
    joined_candidate = " ".join(candidate_tokens)
    ratio = SequenceMatcher(None, joined_query, joined_candidate).ratio()
    substring_boost = 0.14 if joined_query and joined_query in joined_candidate else 0.0
    important_boost = 0.10 if len(overlap) >= min(3, len(query_tokens)) else 0.0
    score = min(1.0, (coverage * 0.62) + (ratio * 0.28) + substring_boost + important_boost)
    if len(candidate_tokens) > max(8, len(query_tokens) * 3) and joined_query not in joined_candidate:
        score = min(score, 0.68)
    return score


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
