from datetime import UTC, datetime

from app.timeutil import iso_utc


def test_iso_utc_appends_z_to_naive_utc() -> None:
    assert iso_utc(datetime(2026, 8, 16, 12, 0, 0)) == "2026-08-16T12:00:00Z"


def test_iso_utc_normalizes_aware_datetime() -> None:
    aware = datetime(2026, 8, 16, 20, 0, 0, tzinfo=UTC)
    assert iso_utc(aware) == "2026-08-16T20:00:00Z"
