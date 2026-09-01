"""Regressões puras da fundação e do parser da Fase 0."""

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from consultor_juridico.application.corpus.catalog import LEI_9784_ACT, LEI_9784_SOURCE
from consultor_juridico.application.corpus.parser import PlanaltoLeiParser
from consultor_juridico.application.corpus.ports import (
    AcquisitionResponse,
    SnapshotRecord,
)
from consultor_juridico.application.corpus.projection import ProvisionTextProjection
from consultor_juridico.application.corpus.services import (
    AcquireOfficialSource,
    MaterializeFromSnapshot,
)
from consultor_juridico.cli.main import app
from consultor_juridico.domain.corpus import (
    LegalStatus,
    ProvisionType,
    SnapshotData,
    SourceDocumentDecodingError,
    UnsupportedSourceStructure,
    VersionIdentity,
    decode_strict,
)

FIXTURES = Path(__file__).parent / "fixtures" / "corpus"
REAL_CAPTURE = (
    Path(__file__).parents[1]
    / "docs/corpus/artifacts/lei-9784-1999-planalto-2026-08-31.raw.html"
)


def _parse(name: str):
    raw = (FIXTURES / name).read_text().encode("windows-1252")
    return PlanaltoLeiParser().parse(raw, encoding="windows-1252")


@pytest.mark.parametrize(
    ("fixture", "stable_key"),
    [
        ("document_root.html", "PREAMBLE"),
        ("chapter_standard.html", "CHAPTER:IV"),
        ("chapter_with_suffix.html", "CHAPTER:XI-A"),
        ("article_ordinal.html", "ARTICLE:1"),
        ("article_decimal.html", "ARTICLE:10"),
        ("article_with_suffix.html", "ARTICLE:10-A"),
        ("caput_with_incisos.html", "ARTICLE:1/CAPUT/INCISO:II"),
        ("unique_paragraph.html", "ARTICLE:1/PARAGRAPH:UNIQUE"),
        ("paragraph_with_incisos.html", "ARTICLE:1/PARAGRAPH:1/INCISO:II"),
        ("multiple_paragraphs.html", "ARTICLE:1/PARAGRAPH:2"),
        ("inline_editorial_note.html", "ARTICLE:1-A/CAPUT"),
        ("explicit_veto.html", "ARTICLE:1/PARAGRAPH:1"),
        ("windows_1252_tail.html", "ARTICLE:1/CAPUT/INCISO:I"),
    ],
)
def test_thirteen_fixture_classes(fixture: str, stable_key: str):
    result = _parse(fixture)
    assert stable_key in {item.stable_key for item in result.provisions}
    assert len(result.coverage) == result.total_dom_paragraphs


def test_article_is_container_and_caput_carries_text():
    result = _parse("article_decimal.html")
    article = next(
        item for item in result.provisions if item.stable_key == "ARTICLE:10"
    )
    caput = next(
        item for item in result.provisions if item.stable_key == "ARTICLE:10/CAPUT"
    )
    assert article.citation_text is None
    assert caput.citation_text == "Art. 10. Texto decimal."


def test_inciso_parent_is_present_in_stable_key():
    result = _parse("paragraph_with_incisos.html")
    keys = {item.stable_key for item in result.provisions}
    assert "ARTICLE:1/PARAGRAPH:1/INCISO:I" in keys


def test_explicit_veto_sets_vetoed_without_device_list():
    result = _parse("explicit_veto.html")
    vetoed = [
        item for item in result.provisions if item.legal_status is LegalStatus.VETOED
    ]
    assert [item.provision_type for item in vetoed] == [ProvisionType.PARAGRAPH]
    assert vetoed[0].citation_text == "§ 1º (VETADO)."


def test_inline_editorial_note_is_preserved():
    result = _parse("inline_editorial_note.html")
    caput = next(
        item for item in result.provisions if item.provision_type is ProvisionType.CAPUT
    )
    assert "(Incluído pela Lei nº 2, de 2001)" in caput.citation_text


def test_windows_1252_byte_0x96_is_en_dash():
    assert decode_strict(b"I \x96 texto", "windows-1252") == "I – texto"


def test_strict_decoding_never_replaces_invalid_bytes():
    with pytest.raises(SourceDocumentDecodingError):
        decode_strict(b"\x81", "windows-1252")


def test_post_html_tail_does_not_change_parsed_tree():
    base = (FIXTURES / "windows_1252_tail.html").read_text().split("</html>")[0]
    raw_a = f"{base}</html><script>f5 A</script>".encode("windows-1252")
    raw_b = f"{base}</html><script>f5 B</script>".encode("windows-1252")
    assert sha256(raw_a).hexdigest() != sha256(raw_b).hexdigest()
    assert PlanaltoLeiParser().parse(raw_a, encoding="windows-1252") == (
        PlanaltoLeiParser().parse(raw_b, encoding="windows-1252")
    )


def test_unrecognized_legal_paragraph_fails_closed():
    raw = (
        "<html><body><p>LEI Nº 1, DE 2000.</p><p>Ementa.</p><p>Promulgação.</p>"
        "<p>CAPÍTULO I GERAL</p><p>Texto jurídico sem classe.</p>"
        "<p>Art. 1º Texto.</p></body></html>"
    ).encode("windows-1252")
    with pytest.raises(UnsupportedSourceStructure, match="não reconhecido"):
        PlanaltoLeiParser().parse(raw, encoding="windows-1252")


def test_real_capture_has_complete_coverage_and_observed_structure():
    result = PlanaltoLeiParser().parse(
        REAL_CAPTURE.read_bytes(), encoding="windows-1252"
    )
    counts = {
        kind: sum(item.provision_type is kind for item in result.provisions)
        for kind in ProvisionType
    }
    assert result.total_dom_paragraphs == 260
    assert result.non_empty_paragraphs == 251
    assert result.consumed_paragraphs == 246
    assert result.explicitly_ignored_paragraphs == 14
    assert counts == {
        ProvisionType.DOCUMENT_ROOT: 1,
        ProvisionType.CHAPTER: 19,
        ProvisionType.ARTICLE: 80,
        ProvisionType.CAPUT: 80,
        ProvisionType.PARAGRAPH: 66,
        ProvisionType.INCISO: 76,
    }


def test_projection_is_plain_one_to_one_official_text():
    parsed = _parse("multiple_paragraphs.html")
    units = ProvisionTextProjection().project(parsed)
    textual = [item for item in parsed.provisions if item.citation_text]
    assert len(units) == len(textual)
    assert all(
        unit.search_text == item.citation_text
        for unit, item in zip(units, textual, strict=True)
    )
    assert all(unit.provision_stable_keys == (unit.unit_key,) for unit in units)


def test_version_hash_is_canonical_and_sensitive_to_versions_and_snapshot():
    base = VersionIdentity("ACT", "a" * 64, "parser", "1", "projection", "1")
    assert base.version_hash == replace(base).version_hash
    assert base.version_hash != replace(base, parser_version="2").version_hash
    assert base.version_hash != replace(base, projection_version="2").version_hash
    assert (
        base.version_hash != replace(base, source_snapshot_sha256="b" * 64).version_hash
    )


class _FakeSnapshots:
    def __init__(self, previous=None):
        self.previous = previous
        self.store_calls = 0

    def latest_for_source(self, source):
        return self.previous

    def store(self, source, response):
        self.store_calls += 1
        return self.previous, False


def test_conditional_304_reuses_immutable_snapshot():
    previous = SnapshotRecord(
        uuid4(),
        uuid4(),
        "a" * 64,
        b"raw",
        3,
        "text/html",
        '"etag"',
        "date",
        SimpleNamespace(isoformat=lambda: "time"),
    )
    snapshots = _FakeSnapshots(previous)
    captured = {}

    class Acquirer:
        def acquire(self, url, *, etag, last_modified):
            captured.update(etag=etag, last_modified=last_modified)
            return AcquisitionResponse(304, None, None, '"etag"', "date")

    result = AcquireOfficialSource(Acquirer(), snapshots).execute(LEI_9784_SOURCE)
    assert result.snapshot is previous
    assert result.reused is True
    assert snapshots.store_calls == 0
    assert captured == {"etag": '"etag"', "last_modified": "date"}


def test_reprojection_is_offline_and_has_no_source_acquirer_dependency():
    raw = (FIXTURES / "article_decimal.html").read_text().encode("windows-1252")
    snapshot = SnapshotData(
        uuid4(), uuid4(), sha256(raw).hexdigest(), raw, "windows-1252"
    )

    class Snapshots:
        def by_sha(self, sha256_hex, encoding):
            assert sha256_hex == snapshot.sha256
            assert encoding == snapshot.encoding
            return snapshot

    class Materializer:
        def materialize(self, **kwargs):
            assert kwargs["snapshot"] is snapshot
            return SimpleNamespace(created=True)

    class UnavailableHttpClient:
        calls = 0

        def acquire(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("HTTP não pode participar da reprojeção")

    unavailable = UnavailableHttpClient()
    result = MaterializeFromSnapshot(
        Snapshots(),
        Materializer(),
        PlanaltoLeiParser(),
        ProvisionTextProjection(),
    ).execute(
        snapshot_sha=snapshot.sha256,
        source=LEI_9784_SOURCE,
        act=LEI_9784_ACT,
    )
    assert result.created is True
    assert unavailable.calls == 0


def test_cli_exposes_foundation_and_phase_one_groups():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "corpus" in result.stdout
    assert "retrieval" in result.stdout
    assert "eval" in result.stdout
    assert "Executa consulta" not in result.stdout
