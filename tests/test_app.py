from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.database import Base, get_db
from app.main import create_app
from app.models import Submission, SubmissionRow, TorobMatch
from app.services.product_search import ProductSearchError, ProductSearchResult
from app.services.torob import TorobClientError, TorobSearchResult


def make_xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["product_name", "price"])
    sheet.append(["رب گوجه روژین", "165000"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def make_multi_row_xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["product_name", "price"])
    sheet.append(["رب گوجه روژین", "165000"])
    sheet.append(["بالم لب", "90000"])
    sheet.append(["شامپو", "120000"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


class FakeProductSearchClient:
    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        return [
            ProductSearchResult(
                source="torob",
                rank=0,
                base_prk="base-1",
                name=f"{query} ترب",
                price=150000,
                price_text="از ۱۵۰۰۰۰ تومان",
                image_url="https://image.example/a.jpg",
                product_url="https://torob.com/p/base-1",
                is_already_added=False,
            ),
            ProductSearchResult(
                source="basalam",
                rank=1,
                base_prk="basalam-2",
                name=f"{query} باسلام",
                price=155000,
                price_text="از ۱۵۵۰۰۰ تومان",
                image_url="https://image.example/b.jpg",
                product_url="https://basalam.com/p/basalam-2",
                is_already_added=False,
            ),
            ProductSearchResult(
                source="torob",
                rank=2,
                base_prk="base-3",
                name=f"{query} ترب سوم",
                price=160000,
                price_text="از ۱۶۰۰۰۰ تومان",
                image_url="https://image.example/c.jpg",
                product_url="https://torob.com/p/base-3",
                is_already_added=False,
            ),
            ProductSearchResult(
                source="basalam",
                rank=3,
                base_prk="basalam-4",
                name=f"{query} باسلام دوم",
                price=165000,
                price_text="از ۱۶۵۰۰۰ تومان",
                image_url="https://image.example/d.jpg",
                product_url="https://basalam.com/p/basalam-4",
                is_already_added=False,
            )
        ]

    async def close(self) -> None:
        return None


class FakeForbiddenProductSearchClient:
    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        raise ProductSearchError("torob_forbidden", "اتصال به ترب مجاز نیست.")

    async def close(self) -> None:
        return None


class FakeBotChallengeProductSearchClient:
    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        raise ProductSearchError(
            "torob_bot_challenge",
            "ترب فعلا درخواست‌های جستجوی خودکار را تایید نمی‌کند.",
        )

    async def close(self) -> None:
        return None


class FakeTimeoutProductSearchClient:
    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        raise ProductSearchError("torob_timeout", "جستجو کامل نشد. دوباره تلاش کن.")

    async def close(self) -> None:
        return None


class FakeTimeoutTorobClient:
    async def search_base_products(self, query: str, size: int = 5, page: int = 0) -> list[TorobSearchResult]:
        raise TorobClientError("torob_timeout", "جستجو کامل نشد. دوباره تلاش کن.")

    async def close(self) -> None:
        return None


class FakeChallengeAfterOneSuccessTorobClient:
    def __init__(self) -> None:
        self.calls = 0

    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        self.calls += 1
        if self.calls > 1:
            raise ProductSearchError("torob_bot_challenge", "gateway challenge")
        return [
            ProductSearchResult(
                source="torob",
                rank=0,
                base_prk="base-1",
                name=f"{query} ترب",
                price=150000,
                price_text="از ۱۵۰۰۰۰ تومان",
                image_url="https://image.example/a.jpg",
                product_url="https://torob.com/p/base-1",
                is_already_added=False,
            )
        ]

    async def close(self) -> None:
        return None


class FakeGatewayNotFoundAfterOneSuccessTorobClient:
    def __init__(self) -> None:
        self.calls = 0

    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        self.calls += 1
        if self.calls > 1:
            raise ProductSearchError("torob_gateway_not_found", "مسیر gateway ترب پیدا نشد.")
        return [
            ProductSearchResult(
                source="torob",
                rank=0,
                base_prk="base-1",
                name=f"{query} ترب",
                price=150000,
                price_text="از ۱۵۰۰۰۰ تومان",
                image_url="https://image.example/a.jpg",
                product_url="https://torob.com/p/base-1",
                is_already_added=False,
            )
        ]

    async def close(self) -> None:
        return None


class FakePagedProductSearchClient:
    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        return [
            ProductSearchResult(
                source="torob",
                rank=0,
                base_prk=f"base-{page}-1",
                name=f"{query} ترب {page}-1",
                price=100000 + page,
                price_text=None,
                image_url=None,
                product_url=f"https://torob.com/p/base-{page}-1",
            ),
            ProductSearchResult(
                source="basalam",
                rank=1,
                base_prk=f"basalam-{page}-1",
                name=f"{query} باسلام {page}-1",
                price=110000 + page,
                price_text=None,
                image_url=None,
                product_url=f"https://basalam.com/p/basalam-{page}-1",
            ),
            ProductSearchResult(
                source="torob",
                rank=2,
                base_prk=f"base-{page}-2",
                name=f"{query} ترب {page}-2",
                price=120000 + page,
                price_text=None,
                image_url=None,
                product_url=f"https://torob.com/p/base-{page}-2",
            ),
            ProductSearchResult(
                source="basalam",
                rank=3,
                base_prk=f"basalam-{page}-2",
                name=f"{query} باسلام {page}-2",
                price=130000 + page,
                price_text=None,
                image_url=None,
                product_url=f"https://basalam.com/p/basalam-{page}-2",
            ),
        ]

    async def close(self) -> None:
        return None


def test_upload_confirm_admin_export(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeProductSearchClient)
    monkeypatch.setattr("app.routes.seller.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.routes.seller.settings.upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr("app.routes.admin.settings.admin_password", "secret")
    monkeypatch.setattr("app.routes.admin.settings.session_secret", "test-cookie")

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    upload = client.post(
        "/uploads",
        data={"store_name": "فروشگاه تست", "seller_phone": "09121234567"},
        files={"file": ("products.xlsx", make_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200
    assert "در حال آماده‌سازی محصولات" in upload.text
    assert "fetch(statusUrl" in upload.text

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission is not None
        assert submission.seller_phone == "09121234567"
        assert submission.original_filename == "products.xlsx"
        assert submission.stored_file_path is not None
        assert (tmp_path / "uploads" / f"{submission.id}-products.xlsx").exists()
        row = submission.rows[0]
        match_id = row.matches[0].id
        second_match_id = row.matches[1].id
        submission_id = submission.id
        row_id = row.id

    status = client.get(f"/submissions/{submission_id}/processing-status")
    assert status.status_code == 204
    assert status.headers["HX-Redirect"] == f"/submissions/{submission_id}/match"

    match_page = client.get(f"/submissions/{submission_id}/match")
    assert match_page.status_code == 200
    assert "رب گوجه روژین ترب" in match_page.text
    assert f'value="{match_id}" checked' not in match_page.text
    assert f'value="{second_match_id}" checked' not in match_page.text
    assert "قیمت ترب: 150,000 تومان" in match_page.text
    assert "قیمت باسلام: 155,000 تومان" in match_page.text
    assert "بیشتر" in match_page.text
    assert 'value="165,000"' in match_page.text
    assert "محصول انتخاب شده" in match_page.text

    confirm = client.post(
        f"/submissions/{submission_id}/confirm",
        data={
            f"selected_{row_id}": [str(match_id), str(second_match_id)],
            f"price_{row_id}": "170000",
            "price_unit": "toman",
        },
    )
    assert confirm.status_code == 200
    assert "کد پیگیری" in confirm.text

    login = client.post("/admin/login", data={"password": "secret"}, follow_redirects=False)
    assert login.status_code == 303

    update = client.post(
        f"/admin/submissions/{submission_id}/shop-id",
        data={"shop_id": "411147"},
        follow_redirects=False,
    )
    assert update.status_code == 303

    export = client.get(f"/admin/submissions/{submission_id}/export.xlsx")
    assert export.status_code == 200
    workbook = load_workbook(BytesIO(export.content))
    sheet = workbook.active
    assert sheet["B2"].value == "فروشگاه تست"
    assert sheet["C2"].value == "09121234567"
    assert sheet["D2"].value == "411147"
    assert sheet["H2"].value == "torob"
    assert sheet["I2"].value == "base-1"
    assert sheet["L2"].value == "170000"
    assert sheet["H3"].value == "basalam"
    assert sheet["I3"].value == "basalam-2"
    assert sheet["L3"].value == "170000"

    detail = client.get(f"/admin/submissions/{submission_id}")
    assert detail.status_code == 200
    assert "09121234567" in detail.text

    listing = client.get("/admin/submissions")
    assert listing.status_code == 200
    assert "09121234567" in listing.text


def test_forbidden_torob_connection_fails_job_with_clean_message(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeForbiddenProductSearchClient)
    monkeypatch.setattr("app.routes.seller.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.routes.seller.settings.upload_dir", str(tmp_path / "uploads"))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    upload = client.post(
        "/uploads",
        data={"store_name": "فروشگاه تست", "seller_phone": ""},
        files={"file": ("products.xlsx", make_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission is not None
        assert submission.status == "failed"
        submission_id = submission.id

    status = client.get(f"/submissions/{submission_id}/processing-status")
    assert status.status_code == 200
    assert status.headers["X-Processing-State"] == "failed"
    assert "اتصال به ترب مجاز نیست" in status.text
    assert "api.torob.com" not in status.text


def test_bot_challenge_fails_job_instead_of_row_errors(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeBotChallengeProductSearchClient)
    monkeypatch.setattr("app.routes.seller.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.routes.seller.settings.upload_dir", str(tmp_path / "uploads"))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    upload = client.post(
        "/uploads",
        data={"store_name": "فروشگاه تست", "seller_phone": ""},
        files={"file": ("products.xlsx", make_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission is not None
        assert submission.status == "failed"
        assert submission.rows[0].error_message is None
        submission_id = submission.id

    status = client.get(f"/submissions/{submission_id}/processing-status")
    assert status.status_code == 200
    assert status.headers["X-Processing-State"] == "failed"
    assert "صفحه بررسی ربات" in status.text
    assert "فایل اکسل نیست" in status.text


def test_timeout_before_first_success_fails_job_with_vpn_hint(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeTimeoutProductSearchClient)
    monkeypatch.setattr("app.routes.seller.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.routes.seller.settings.upload_dir", str(tmp_path / "uploads"))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    upload = client.post(
        "/uploads",
        data={"store_name": "فروشگاه تست", "seller_phone": ""},
        files={"file": ("products.xlsx", make_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission is not None
        assert submission.status == "failed"
        assert submission.rows[0].error_message is None
        submission_id = submission.id

    status = client.get(f"/submissions/{submission_id}/processing-status")
    assert status.status_code == 200
    assert status.headers["X-Processing-State"] == "failed"
    assert "VPN" in status.text
    assert "فایل اکسل نیست" in status.text


def test_gateway_challenge_after_success_keeps_partial_results(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeChallengeAfterOneSuccessTorobClient)
    monkeypatch.setattr("app.routes.seller.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.routes.seller.settings.upload_dir", str(tmp_path / "uploads"))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    upload = client.post(
        "/uploads",
        data={"store_name": "فروشگاه تست", "seller_phone": ""},
        files={"file": ("products.xlsx", make_multi_row_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission is not None
        assert submission.status == "ready"
        assert submission.rows[0].matches
        assert "ترب کامل نشد" in submission.rows[1].error_message
        assert "کمی بعد تلاش مجدد" in submission.rows[2].error_message
        submission_id = submission.id

    status = client.get(f"/submissions/{submission_id}/processing-status")
    assert status.status_code == 204
    assert status.headers["HX-Redirect"] == f"/submissions/{submission_id}/match"


def test_gateway_404_after_success_keeps_partial_results(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeGatewayNotFoundAfterOneSuccessTorobClient)
    monkeypatch.setattr("app.routes.seller.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.routes.seller.settings.upload_dir", str(tmp_path / "uploads"))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    upload = client.post(
        "/uploads",
        data={"store_name": "فروشگاه تست", "seller_phone": ""},
        files={"file": ("products.xlsx", make_multi_row_xlsx(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert upload.status_code == 200

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission is not None
        assert submission.status == "ready"
        assert submission.rows[0].matches
        assert "gateway" in submission.rows[1].error_message
        assert "کمی بعد تلاش مجدد" in submission.rows[2].error_message
        submission_id = submission.id

    status = client.get(f"/submissions/{submission_id}/processing-status")
    assert status.status_code == 204
    assert status.headers["HX-Redirect"] == f"/submissions/{submission_id}/match"


def test_admin_torob_health_reports_timeout(monkeypatch) -> None:
    monkeypatch.setattr("app.routes.admin.TorobClient", FakeTimeoutTorobClient)
    monkeypatch.setattr("app.routes.admin.settings.admin_password", "secret")
    monkeypatch.setattr("app.routes.admin.settings.session_secret", "test-cookie")

    app = create_app()
    client = TestClient(app)

    login = client.post("/admin/login", data={"password": "secret"}, follow_redirects=False)
    assert login.status_code == 303

    health = client.get("/admin/torob-health")

    assert health.status_code == 503
    assert "torob_timeout" in health.text
    assert "VPN" in health.text


def test_retry_row_search_replaces_error_with_results(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakeProductSearchClient)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with TestingSessionLocal() as db:
        submission = Submission(store_name="فروشگاه تست", status="ready", total_rows=1)
        db.add(submission)
        db.commit()
        db.refresh(submission)
        row = SubmissionRow(
            submission_id=submission.id,
            input_row=1,
            input_product_name="رب گوجه روژین",
            input_price="165000",
            error_message="جستجو کامل نشد. دوباره تلاش کن.",
        )
        db.add(row)
        db.commit()
        row_id = row.id

    retry = client.post(f"/rows/{row_id}/retry")

    assert retry.status_code == 200
    assert "رب گوجه روژین ترب" in retry.text
    assert "تلاش مجدد" not in retry.text


def test_load_more_row_matches_appends_next_batch(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.routes.seller.ProductSearchClient", FakePagedProductSearchClient)

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with TestingSessionLocal() as db:
        submission = Submission(store_name="فروشگاه تست", status="ready", total_rows=1)
        db.add(submission)
        db.commit()
        db.refresh(submission)
        row = SubmissionRow(
            submission_id=submission.id,
            input_row=1,
            input_product_name="رب",
            has_more_matches=True,
            next_search_page=1,
        )
        row.matches = [
            TorobMatch(source="torob", base_prk="base-0-1", name="قبلی ۱", price=1, rank=0),
            TorobMatch(source="basalam", base_prk="basalam-0-1", name="قبلی ۲", price=2, rank=1),
            TorobMatch(source="torob", base_prk="base-0-2", name="قبلی ۳", price=3, rank=2),
            TorobMatch(source="basalam", base_prk="basalam-0-2", name="قبلی ۴", price=4, rank=3),
        ]
        db.add(row)
        db.commit()
        row_id = row.id

    response = client.post(f"/rows/{row_id}/more")

    assert response.status_code == 200
    assert "رب ترب 1-1" in response.text
    assert "price-unit-card" in response.text
    with TestingSessionLocal() as db:
        row = db.query(SubmissionRow).filter(SubmissionRow.id == row_id).first()
        assert len(row.matches) == 8
        assert row.next_search_page == 2


def test_confirm_converts_rial_prices_to_toman(monkeypatch, tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    with TestingSessionLocal() as db:
        submission = Submission(store_name="فروشگاه تست", status="ready", total_rows=1)
        db.add(submission)
        db.commit()
        db.refresh(submission)
        row = SubmissionRow(submission_id=submission.id, input_row=1, input_product_name="رب", input_price=None)
        db.add(row)
        db.commit()
        db.refresh(row)
        row.matches.append(
            TorobMatch(
                source="torob",
                base_prk="base-rial",
                name="رب ترب",
                price=120000,
                rank=0,
            )
        )
        db.commit()
        submission_id = submission.id
        row_id = row.id
        match_id = row.matches[0].id

    confirm = client.post(
        f"/submissions/{submission_id}/confirm",
        data={f"selected_{row_id}": str(match_id), f"price_{row_id}": "1200000", "price_unit": "rial"},
    )
    assert confirm.status_code == 200

    with TestingSessionLocal() as db:
        submission = db.query(Submission).first()
        assert submission.rows[0].final_price == "120000"


def test_index_has_loading_submit_state() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "upload-form" in response.text
    assert "file-drop" in response.text
    assert "هنوز فایلی انتخاب نشده است" in response.text
    assert "برای شروع، فایل اکسل محصولات را انتخاب کن" in response.text
    assert "در حال پردازش فایل" in response.text
    assert "fetch(form.action" in response.text
    assert "شماره موبایل، اختیاری" in response.text
    assert "وارد کردن دسته جمعی محصولات به ترب، برای فروشندگان حضوری" in response.text
    assert "این نسخه آزمایشی هست؛ لطفا شمارت رو بذار" in response.text


def test_health_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.text == "ok"
