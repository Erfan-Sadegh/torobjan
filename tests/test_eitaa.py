from app.services.eitaa import extract_eitaa_products, score_product_match


def test_extract_eitaa_products_groups_text_and_following_photos() -> None:
    messages = [
        {
            "message_id": 120,
            "date": 1755439769,
            "text": "متن معرفی کانال بدون قیمت",
        },
        {
            "message_id": 119,
            "date": 1755439679,
            "text": "کتونی نایک وودو\r\n\r\nسایز: 37 تا 40\r\n\r\nقیمت: 668٬000 تومان\r\nارتباط: @seller",
        },
        {
            "message_id": 118,
            "date": 1755439656,
            "photo": [
                {"file_id": "small", "width": 90, "height": 90},
                {"file_id": "large", "width": 800, "height": 800},
            ],
        },
    ]

    products = extract_eitaa_products(messages, max_products=10)

    assert len(products) == 1
    assert products[0].product_name == "کتونی نایک وودو"
    assert products[0].price_toman == "668000"
    assert products[0].best_photo.file_id == "large"


def test_score_product_match_is_conservative() -> None:
    assert score_product_match("کتونی نایک وودو", "کتونی نایک مدل وودو") >= 0.84
    assert score_product_match("تخم مرغ ۳۰ عددی", "تخم مرغ بسته ۳۰ عددی") >= 0.84
    assert score_product_match("گوجه فرنگی درجه یک", "گوجه فرنگی بوته ای درجه یک") >= 0.84
    assert score_product_match("کتونی نایک وودو", "دمپایی روفرشی زنانه") < 0.84
    assert score_product_match("پیاز زرد", "بذر پیاز زرد سوپرکس تاکی") == 0
    assert score_product_match("سیب زرد", "نهال سیب زرد فرانسه") == 0
    assert score_product_match("کیوی درجه یک", "کیوی خشک درجه یک ۲۰۰ گرم") == 0


def test_extract_eitaa_products_handles_market_price_lists() -> None:
    messages = [
        {
            "message_id": 5281,
            "date": 1755439769,
            "text": """📅 لیست تره‌بار امروز

🍅 گوجه فرنگی درجه یک — ۳۹
🥒 خیار تازه درجه یک ــــ ۹۵
🍄 قـــــارچ فـــله ــــ ۲۸۰
""",
        },
        {
            "message_id": 5282,
            "date": 1755439769,
            "text": """💳 قیمت محصولات پروتئینی امروز 👇

🔸 مـــــرغ بهـــــــــاران : ۳۶۹
🔹 گوشت چرخ‌کرده مخلوط : ۱/۱۵۰
""",
        },
    ]

    products = extract_eitaa_products(messages, max_products=10)

    assert [(item.product_name, item.price_toman) for item in products] == [
        ("مـــــرغ بهـــــــــاران", "369000"),
        ("گوشت چرخ کرده مخلوط", "1150000"),
        ("گوجه فرنگی درجه یک", "39000"),
        ("خیار تازه درجه یک", "95000"),
        ("قـــــارچ فـــله", "280000"),
    ]


def test_extract_eitaa_products_prefers_contextual_store_price() -> None:
    messages = [
        {
            "message_id": 5270,
            "date": 1755439769,
            "text": """پوشک مولفیکس سایز 4/3/2/1

💳 قیمت بازار 👈 ۳۴۰ ❌
🔖 قیمت کوثر 👈 ۱۳۶ ✅
""",
        }
    ]

    products = extract_eitaa_products(messages, max_products=10)

    assert len(products) == 1
    assert products[0].product_name == "پوشک مولفیکس سایز 4/3/2/1"
    assert products[0].price_toman == "136000"


def test_extract_eitaa_products_keeps_product_name_across_price_detail_lines() -> None:
    messages = [
        {
            "message_id": 5260,
            "date": 1755439769,
            "text": """تخم مرغ فله درجه یک

درشت بار، سالم، یکدست
تاریخ روز
شانه ۳۰ عددی 👉 کیلویی «۱۹۹»
قیمت هر شانه حدود ۴۰۰ تومن
""",
        }
    ]

    products = extract_eitaa_products(messages, max_products=10)

    assert len(products) == 1
    assert products[0].product_name == "تخم مرغ فله درجه یک"
    assert products[0].price_toman == "400000"
