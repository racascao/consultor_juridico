"""Testes do hash aplicado diretamente aos bytes canônicos."""

from consultor_juridico.ingestion.hasher import sha256_hex


def test_sha256_is_deterministic_and_byte_sensitive():
    payload = b"\x00\xffConstituicao"
    assert sha256_hex(payload) == sha256_hex(payload)
    assert len(sha256_hex(payload)) == 64
    assert sha256_hex(payload) != sha256_hex(payload + b"\n")
