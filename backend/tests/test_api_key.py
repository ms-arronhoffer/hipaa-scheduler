"""API-key generation and hashing invariants.

Contract: keys are `hs_`-prefixed, only their sha256 is stored, and the
displayed short-prefix is deterministic and non-secret.
"""
import hashlib

from app.auth.api_key import PREFIX, generate, hash_key


class TestGenerate:
    def test_prefix(self):
        plaintext, short, _ = generate()
        assert plaintext.startswith(PREFIX)
        assert short.startswith(PREFIX)

    def test_short_prefix_is_11_chars(self):
        _, short, _ = generate()
        assert len(short) == 11

    def test_short_prefix_is_deterministic_slice(self):
        plaintext, short, _ = generate()
        assert plaintext[:11] == short

    def test_hash_is_sha256_of_plaintext(self):
        plaintext, _, digest = generate()
        assert digest == hashlib.sha256(plaintext.encode()).hexdigest()
        assert len(digest) == 64

    def test_keys_are_unique(self):
        keys = {generate()[0] for _ in range(50)}
        assert len(keys) == 50


class TestHashKey:
    def test_matches_generate_output(self):
        plaintext, _, digest = generate()
        assert hash_key(plaintext) == digest

    def test_different_input_different_hash(self):
        assert hash_key("hs_a") != hash_key("hs_b")

    def test_stable(self):
        assert hash_key("hs_stable") == hash_key("hs_stable")
