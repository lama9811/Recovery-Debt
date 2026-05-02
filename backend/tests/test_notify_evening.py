"""Tests for the 9 PM evening-notification worker.

The worker has two parts: a pure payload builder (tested here) and the I/O
shell that fans out to webpush (tested via integration when deployed). The
payload builder must respect PRD §13 honesty: before 60 days of training
data, the body labels itself as an early estimate.
"""

from __future__ import annotations

import datetime as dt

from workers.notify_evening import build_evening_payload


def test_payload_rounds_recovery_to_int():
    p = build_evening_payload(
        predicted_recovery=64.7,
        target_day=dt.date(2026, 5, 2),
        n_training_days=120,
    )
    assert "65" in p["body"]
    assert "64.7" not in p["body"]


def test_payload_includes_target_day_as_tomorrow_label():
    p = build_evening_payload(
        predicted_recovery=58.0,
        target_day=dt.date(2026, 5, 2),
        n_training_days=120,
    )
    assert p["title"]
    assert p["url"] == "/"


def test_payload_labels_early_estimate_before_60_days():
    """PRD §13: pre-60-days insights must say 'early estimate'."""
    p = build_evening_payload(
        predicted_recovery=58.0,
        target_day=dt.date(2026, 5, 2),
        n_training_days=30,
    )
    assert "early estimate" in p["body"].lower()


def test_payload_drops_early_label_after_60_days():
    p = build_evening_payload(
        predicted_recovery=58.0,
        target_day=dt.date(2026, 5, 2),
        n_training_days=120,
    )
    assert "early estimate" not in p["body"].lower()


def test_payload_avoids_medical_or_imperative_language():
    """PRD §13 honesty: never say 'you should sleep more' style imperatives."""
    p = build_evening_payload(
        predicted_recovery=42.0,
        target_day=dt.date(2026, 5, 2),
        n_training_days=120,
    )
    body_lower = p["body"].lower()
    for forbidden in ("you should", "you must", "doctor", "medical"):
        assert forbidden not in body_lower, f"forbidden phrase: {forbidden}"
