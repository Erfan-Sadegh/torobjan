from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Store, Submission, SubmissionRow, SubmissionSelection, TorobMatch
from app.services.eitaa_updates import create_eitaa_update_preview
from app.services.torob import TorobSearchResult


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'updates.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _known_store_with_product(db):
    store = Store(
        name="فروشگاه تست",
        seller_phone="09120000000",
        shop_id="411488",
        eitaa_channel_id="@regaal",
        eitaa_last_update_id=84,
    )
    submission = Submission(
        store=store,
        store_name="فروشگاه تست",
        seller_phone="09120000000",
        shop_id="411488",
        source="eitaa",
        source_ref="@regaal",
        operation="add",
        status="submitted",
        price_unit="toman",
    )
    row = SubmissionRow(
        submission=submission,
        input_row=1,
        input_product_name="کفش تست",
        input_price="650000",
        final_price="650000",
        source_message_id="124",
    )
    match = TorobMatch(
        row=row,
        source="torob",
        rank=0,
        base_prk="shoe-base-rk",
        name="کفش تست ترب",
        price=650000,
        price_text="650,000 تومان",
        image_url="https://image.example/shoe.jpg",
        product_url="https://torob.com/p/shoe-base-rk",
    )
    db.add_all([store, submission, row, match])
    db.flush()
    row.selected_match_id = match.id
    db.add(SubmissionSelection(row_id=row.id, match_id=match.id, final_price="650000"))
    db.flush()
    return store


def test_eitaa_update_preview_reuses_known_message_match_and_advances_store_cursor(tmp_path) -> None:
    """Non-developer meaning: edited post 124 was already connected to a Torob product, so keep that product and only preview the new price."""
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as db:
        store = _known_store_with_product(db)
        update = {
            "update_id": 85,
            "edited_channel_post": {
                "message_id": 124,
                "date": 1781681754,
                "edit_date": 1781682789,
                "chat": {"username": "regaal"},
                "text": "کفش تست - 750000 تومان",
            },
        }

        result = create_eitaa_update_preview(db, store, [update])
        db.commit()

        assert result.processed_update_count == 1
        assert result.preview_submission_id is not None
        assert store.eitaa_last_update_id == 85

        preview = db.get(Submission, result.preview_submission_id)
        assert preview is not None
        assert preview.store_id == store.id
        assert preview.operation == "price_update"
        assert preview.source == "eitaa_update"
        assert preview.source_ref == "@regaal"
        assert preview.status == "ready"
        assert preview.total_rows == 1
        assert preview.selected_rows == 1

        row = preview.rows[0]
        assert row.operation == "price_update"
        assert row.source_message_id == "124"
        assert row.input_product_name == "کفش تست"
        assert row.input_price == "750000"
        assert row.final_price == "750000"
        assert len(row.selections) == 1
        assert row.selections[0].final_price == "750000"
        assert row.selections[0].match.base_prk == "shoe-base-rk"


def test_eitaa_update_preview_marks_unknown_message_with_torob_candidates_as_new_product(tmp_path) -> None:
    """Non-developer meaning: if an Eitaa update is not one of the store's old products but Torob has candidates, show it as a new product the seller can add."""
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as db:
        store = Store(
            name="فروشگاه تست",
            seller_phone="09120000000",
            shop_id="411488",
            eitaa_channel_id="@regaal",
            eitaa_last_update_id=84,
        )
        db.add(store)
        db.flush()
        update = {
            "update_id": 86,
            "channel_post": {
                "message_id": 125,
                "date": 1781683000,
                "chat": {"username": "regaal"},
                "text": "کیف تست - 880000 تومان",
            },
        }
        torob_candidate = TorobSearchResult(
            rank=0,
            base_prk="bag-base-rk",
            name="کیف تست ترب",
            price=880000,
            price_text="880,000 تومان",
            image_url="https://image.example/bag.jpg",
            product_url="https://torob.com/p/bag-base-rk",
            is_already_added=False,
        )

        result = create_eitaa_update_preview(
            db,
            store,
            [update],
            torob_results_by_name={"کیف تست": [torob_candidate]},
        )
        db.commit()

        assert result.processed_update_count == 1
        assert result.preview_submission_id is not None
        assert store.eitaa_last_update_id == 86

        preview = db.get(Submission, result.preview_submission_id)
        assert preview is not None
        assert preview.operation == "price_update"
        assert preview.total_rows == 1
        assert preview.selected_rows == 0
        row = preview.rows[0]
        assert row.operation == "add"
        assert row.input_product_name == "کیف تست"
        assert row.input_price == "880000"
        assert row.final_price == "880000"
        assert row.selections == []
        assert row.error_message is None
        assert row.matches[0].base_prk == "bag-base-rk"


def test_eitaa_update_preview_marks_unknown_message_without_torob_candidates_for_review(tmp_path) -> None:
    """Non-developer meaning: if the update is neither an old product nor searchable in Torob, keep it in the review section instead of pretending it is ready."""
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as db:
        store = Store(
            name="فروشگاه تست",
            seller_phone="09120000000",
            shop_id="411488",
            eitaa_channel_id="@regaal",
            eitaa_last_update_id=84,
        )
        db.add(store)
        db.flush()
        update = {
            "update_id": 86,
            "channel_post": {
                "message_id": 125,
                "date": 1781683000,
                "chat": {"username": "regaal"},
                "text": "کیف تست - 880000 تومان",
            },
        }

        result = create_eitaa_update_preview(db, store, [update], torob_results_by_name={"کیف تست": []})
        db.commit()

        assert result.processed_update_count == 1
        assert result.preview_submission_id is not None
        assert store.eitaa_last_update_id == 86

        preview = db.get(Submission, result.preview_submission_id)
        assert preview is not None
        assert preview.operation == "price_update"
        assert preview.total_rows == 1
        assert preview.selected_rows == 0
        row = preview.rows[0]
        assert row.operation == "needs_review"
        assert row.input_product_name == "کیف تست"
        assert row.input_price == "880000"
        assert row.final_price == "880000"
        assert row.matches == []
        assert row.selections == []
        assert row.error_message


def test_eitaa_update_preview_ignores_old_updates_without_moving_cursor_back(tmp_path) -> None:
    """Non-developer meaning: if we already processed update 90, an older update 89 must not change the saved cursor."""
    SessionLocal = _session_factory(tmp_path)
    with SessionLocal() as db:
        store = Store(name="فروشگاه تست", eitaa_channel_id="@regaal", eitaa_last_update_id=90)
        db.add(store)
        db.flush()

        result = create_eitaa_update_preview(
            db,
            store,
            [
                {
                    "update_id": 89,
                    "edited_channel_post": {
                        "message_id": 124,
                        "text": "کفش تست - 760000 تومان",
                    },
                }
            ],
        )
        db.commit()

        assert result.processed_update_count == 0
        assert result.preview_submission_id is None
        assert store.eitaa_last_update_id == 90
