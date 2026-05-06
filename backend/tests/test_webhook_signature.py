"""WHOOP v2 webhook signature verification.

v2 spec: base64(HMAC-SHA256(timestamp_header + raw_body, client_secret)),
sent via two headers: `X-WHOOP-Signature` and `X-WHOOP-Signature-Timestamp`.
v1's hex-only single-header scheme was removed when v1 webhooks were sunset.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from api.webhooks import _verify_signature


def _sign(secret: str, body: bytes, timestamp: str) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_valid_signature_passes() -> None:
    secret = "supersecret"
    body = (
        b'{"user_id":456,"id":"550e8400-e29b-41d4-a716-446655440000",'
        b'"type":"sleep.updated","trace_id":"abc"}'
    )
    ts = "1714838400000"
    sig = _sign(secret, body, ts)
    assert _verify_signature(secret, body, sig, ts) is True


def test_tampered_body_fails() -> None:
    secret = "supersecret"
    body = b'{"user_id":456,"type":"sleep.updated"}'
    ts = "1714838400000"
    sig = _sign(secret, body, ts)
    tampered = b'{"user_id":999,"type":"sleep.updated"}'
    assert _verify_signature(secret, tampered, sig, ts) is False


def test_wrong_timestamp_fails() -> None:
    secret = "supersecret"
    body = b'{"type":"recovery.updated"}'
    sig = _sign(secret, body, "1714838400000")
    assert _verify_signature(secret, body, sig, "1714838500000") is False


def test_empty_headers_fail() -> None:
    secret = "supersecret"
    body = b'{}'
    assert _verify_signature(secret, body, "", "1714838400000") is False
    assert _verify_signature(secret, body, "abc", "") is False
