from app.services.basalam import parse_basalam_results


def test_parse_basalam_results_converts_rial_price_to_toman() -> None:
    data = {
        "products": [
            {
                "id": 14764302,
                "name": "رب گوجه باسلام",
                "price": 2480000.0,
                "photo": {"MEDIUM": "https://image.example/b.jpg"},
            }
        ]
    }

    results = parse_basalam_results(data, size=2)

    assert len(results) == 1
    assert results[0].product_id == "14764302"
    assert results[0].price == 248000
    assert results[0].product_url == "https://basalam.com/p/14764302"
