"""Generate a VAPID keypair for Web Push.

Writes:
  vapid_private.pem  — keep secret, paste into VAPID_PRIVATE_KEY (Railway)
  vapid_public.txt   — paste into NEXT_PUBLIC_VAPID_PUBLIC_KEY (Vercel)

Run:  python -m scripts.generate_vapid

The keys are NIST P-256 (prime256v1) ECDSA, the curve required by the
Web Push protocol. The public key is encoded as URL-safe base64 of the
raw uncompressed point, which is the format `pushManager.subscribe`
expects for `applicationServerKey`.
"""

from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

OUT_DIR = Path(__file__).resolve().parent.parent
PRIV_PATH = OUT_DIR / "vapid_private.pem"
PUB_PATH = OUT_DIR / "vapid_public.txt"


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIV_PATH.write_bytes(pem)

    pub_numbers = private_key.public_key().public_numbers()
    raw = (
        b"\x04"
        + pub_numbers.x.to_bytes(32, "big")
        + pub_numbers.y.to_bytes(32, "big")
    )
    pub_b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    PUB_PATH.write_text(pub_b64 + "\n")

    print("Wrote:")
    print(f"  {PRIV_PATH}  (PRIVATE — backend env VAPID_PRIVATE_KEY)")
    print(f"  {PUB_PATH}   (PUBLIC  — frontend env NEXT_PUBLIC_VAPID_PUBLIC_KEY)")
    print()
    print("Public key (copy into Vercel env NEXT_PUBLIC_VAPID_PUBLIC_KEY):")
    print(f"  {pub_b64}")


if __name__ == "__main__":
    main()
