"""Verification-status governance rules (mirrors migration 004; pure, no I/O).

Vocabulary matches the CHECK constraints added by migration 002. A record may be presented as
verified ONLY when its status is 'official_verified', which in turn requires a recorded
source_document_ref. A checksum or a reachable domain is not evidence for a record.
"""
from __future__ import annotations

STATUSES = ("official_verified", "externally_referenced", "provisional", "unverified", "deprecated")
VERIFIED = "official_verified"

# Display wording for the UI/API; only VERIFIED may be shown as "verified".
LABELS = {
    "official_verified": "Verified against an official source",
    "externally_referenced": "Referenced from an external (non-state) source",
    "provisional": "Provisional - not yet verified against an official document",
    "unverified": "Unverified",
    "deprecated": "Deprecated",
}


def is_verified(status: str | None) -> bool:
    return status == VERIFIED


def validate_transition(old: str | None, new: str, source_document_ref: str | None) -> None:
    """Raise ValueError if moving a record from `old` to `new` breaks a governance rule."""
    if new not in STATUSES:
        raise ValueError(f"unknown verification status '{new}'")
    if old is not None and old not in STATUSES:
        raise ValueError(f"unknown verification status '{old}'")
    if old == "deprecated" and new != "deprecated":
        raise ValueError("a deprecated record cannot change status")
    if new == VERIFIED and not (source_document_ref and source_document_ref.strip()):
        raise ValueError("official_verified requires a source_document_ref")
