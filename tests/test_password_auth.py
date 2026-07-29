"""Local username/password auth (ADR-026) — replaces Google sign-in.

Precision-critical: these prove the password is never stored recoverably, that a wrong
password never authenticates, and that a bad username costs the same work as a bad
password (no user enumeration by timing or by error text).
"""

import pytest

import backend.auth as auth_mod
from backend.auth import (
    AuthUser,
    authenticate,
    hash_password,
    parse_users,
    verify_password,
)


def test_hash_is_salted_and_never_contains_the_password() -> None:
    encoded = hash_password("adminuser123")
    assert "adminuser123" not in encoded
    assert encoded.startswith("scrypt$")
    # Salted: the same password hashes differently every time.
    assert encoded != hash_password("adminuser123")


def test_verify_accepts_the_right_password_and_rejects_others() -> None:
    encoded = hash_password("adminuser123")
    assert verify_password("adminuser123", encoded) is True
    assert verify_password("adminuser124", encoded) is False
    assert verify_password("", encoded) is False
    assert verify_password("ADMINUSER123", encoded) is False  # case matters


@pytest.mark.parametrize(
    "malformed",
    ["", "not-a-hash", "scrypt$only$three$parts", "bcrypt$16384$8$1$c2FsdA==$a2V5", "$$$$$"],
)
def test_verify_rejects_malformed_stored_hashes_instead_of_crashing(malformed: str) -> None:
    assert verify_password("adminuser123", malformed) is False


def test_parse_users_reads_username_hash_pairs() -> None:
    admin = hash_password("adminuser123")
    jake = hash_password("s3cret")
    users = parse_users([f"admin:{admin}", f"jake:{jake}"])
    assert set(users) == {"admin", "jake"}
    # The hash contains '$' and base64 — only the FIRST colon separates name from hash.
    assert users["admin"] == admin


def test_parse_users_ignores_blank_and_malformed_entries() -> None:
    assert parse_users(["", "   ", "no-colon-here"]) == {}


def test_authenticate_returns_the_user_on_correct_credentials() -> None:
    users = parse_users([f"admin:{hash_password('adminuser123')}"])
    user = authenticate("admin", "adminuser123", users)
    assert isinstance(user, AuthUser)
    assert user.username == "admin"


def test_authenticate_rejects_wrong_password_and_unknown_user() -> None:
    users = parse_users([f"admin:{hash_password('adminuser123')}"])
    assert authenticate("admin", "wrong", users) is None
    assert authenticate("nobody", "adminuser123", users) is None
    assert authenticate("", "", users) is None


def test_authenticate_is_case_insensitive_on_username_only() -> None:
    # Usernames are identities, not secrets — typing "Admin" should sign you in.
    users = parse_users([f"admin:{hash_password('adminuser123')}"])
    assert authenticate("ADMIN", "adminuser123", users) is not None
    assert authenticate("admin", "ADMINUSER123", users) is None  # password stays exact


def test_unknown_user_still_does_the_hash_work(monkeypatch: pytest.MonkeyPatch) -> None:
    # No-such-user must not short-circuit, or response timing leaks which usernames exist.
    calls: list[str] = []
    real = auth_mod.verify_password

    def counting(password: str, encoded: str) -> bool:
        calls.append(encoded)
        return real(password, encoded)

    monkeypatch.setattr(auth_mod, "verify_password", counting)
    users = parse_users([f"admin:{hash_password('adminuser123')}"])
    assert auth_mod.authenticate("ghost", "whatever", users) is None
    assert len(calls) == 1  # a dummy verify still ran
