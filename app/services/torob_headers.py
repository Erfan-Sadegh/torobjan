from __future__ import annotations

import httpx

from app.settings import settings


def build_torob_request_headers(
    referer: str = "https://torob.com/",
    *,
    content_type: str | None = None,
) -> dict[str, str]:
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,fa;q=0.8",
        "origin": "https://torob.com",
        "referer": referer,
        "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36"
        ),
    }
    if content_type:
        headers["Content-Type"] = content_type
    if settings.torob_proxy_token:
        headers["x-proxy-token"] = settings.torob_proxy_token
    if settings.torob_iw1_header:
        headers["x-iw1"] = settings.torob_iw1_header
    if settings.torob_cookie:
        headers["cookie"] = settings.torob_cookie
    if settings.torob_csrf_token:
        headers["x-csrftoken"] = settings.torob_csrf_token
    return headers


def is_torob_bot_challenge(response: httpx.Response) -> bool:
    if response.status_code == 490:
        return True
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return False
    text = response.text[:500]
    return "آیا شما یک ربات هستید" in text or "robot" in text.lower()
