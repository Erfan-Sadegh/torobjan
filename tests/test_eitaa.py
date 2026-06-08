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
    assert score_product_match("کتونی نایک وودو", "کتونی نایک مدل وودو") >= 0.72
    assert score_product_match("کتونی نایک وودو", "دمپایی روفرشی زنانه") < 0.72
