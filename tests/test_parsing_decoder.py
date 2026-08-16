"""Testes unitários do decoding íntegro e estrito."""

import hashlib
import uuid

import pytest

from consultor_juridico.parsing import (
    PLANALTO_CONSTITUTION_ENCODING,
    SourceDocumentDecodingError,
    SourceDocumentIntegrityError,
    decode_raw_document,
)


def _decode(payload: bytes, **overrides):
    values = {
        "source_document_id": uuid.uuid4(),
        "raw_bytes": payload,
        "expected_sha256": hashlib.sha256(payload).hexdigest(),
    }
    values.update(overrides)
    return decode_raw_document(**values)


def test_validates_sha_before_decoding():
    payload = b"Constitui\xe7\xe3o"
    decoded = _decode(payload)

    assert decoded.content_hash_sha256 == hashlib.sha256(payload).hexdigest()
    assert decoded.text == "Constituição"
    assert decoded.encoding == PLANALTO_CONSTITUTION_ENCODING


def test_rejects_incorrect_sha():
    with pytest.raises(SourceDocumentIntegrityError, match="Integridade"):
        _decode(b"payload", expected_sha256="0" * 64, encoding="ascii")


def test_windows_1252_preserves_typographic_apostrophe():
    decoded = _decode(b"Carlos De\x92Carli")

    assert decoded.text == "Carlos De’Carli"
    assert "\ufffd" not in decoded.text


def test_strict_decoding_failure_is_explicit():
    with pytest.raises(SourceDocumentDecodingError, match="estrito"):
        _decode(b"texto \x92", encoding="utf-8")


def test_does_not_normalize_or_discard_content():
    payload = b"  linha\r\nConstitui\xe7\xe3o\xa0Federal  "
    decoded = _decode(payload)

    assert decoded.text == "  linha\r\nConstituição\xa0Federal  "
    assert decoded.text.encode(PLANALTO_CONSTITUTION_ENCODING) == payload


def test_integrity_failure_precedes_decoding_failure():
    with pytest.raises(SourceDocumentIntegrityError):
        _decode(b"\x92", expected_sha256="incorrect", encoding="utf-8")
