"""Regressões do corpus contextual sem banco, rede, embedding ou LLM."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from consultor_juridico.application.corpus import (
    BuildCorpusUseCase,
    DuplicateProvisionStableKey,
    MaterializeCorpusUseCase,
    RematerializeCorpusFromSnapshotUseCase,
    SearchUnitBuilder,
    validate_unique_provision_keys,
)
from consultor_juridico.application.corpus.ports import MaterializedCorpus
from consultor_juridico.domain import (
    ParsedAct,
    ParsedCorpus,
    ParsedMetadata,
    ParsedProvision,
    ProvisionType,
    SearchUnitType,
    SourceCapture,
    SourceSnapshotIntegrityError,
    SourceSnapshotNotFound,
    act_version_hash,
    provision_stable_key,
)
from consultor_juridico.infrastructure.corpus.parser import (
    PARSER_VERSION,
    ConstitutionCorpusParser,
)

FIXTURE = Path("tests/fixtures/corpus/contextual_constitution.html")
HISTORICAL_FIXTURE = Path(
    "tests/fixtures/corpus/historical_redactions_constitution.html"
)


def provision(
    key: str,
    kind: ProvisionType,
    order: int,
    text: str,
    *children: ParsedProvision,
    label: str | None = None,
) -> ParsedProvision:
    return ParsedProvision(key, kind, label, order, text, f"block:{order}", children)


def parsed_cf() -> ParsedAct:
    perpetual = provision(
        "CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B",
        ProvisionType.ALINEA,
        6,
        "b) de caráter perpétuo;",
        label="b",
    )
    penalties = provision(
        "CF88/ARTICLE:5/INCISO:XLVII",
        ProvisionType.INCISO,
        5,
        "XLVII - não haverá penas:",
        perpetual,
        label="XLVII",
    )
    house = provision(
        "CF88/ARTICLE:5/INCISO:XI",
        ProvisionType.INCISO,
        4,
        "XI - a casa é asilo inviolável do indivíduo, salvo flagrante delito, "
        "desastre, socorro ou determinação judicial, sem consentimento.",
        label="XI",
    )
    article5 = provision(
        "CF88/ARTICLE:5",
        ProvisionType.ARTICLE,
        3,
        "Art. 5º",
        house,
        penalties,
        label="5",
    )
    optional = provision(
        "CF88/ARTICLE:14/PARAGRAPH:1/INCISO:II",
        ProvisionType.INCISO,
        10,
        "II - facultativos para:",
        provision(
            "CF88/ARTICLE:14/PARAGRAPH:1/INCISO:II/ALINEA:A",
            ProvisionType.ALINEA,
            11,
            "a) os analfabetos;",
            label="a",
        ),
        provision(
            "CF88/ARTICLE:14/PARAGRAPH:1/INCISO:II/ALINEA:B",
            ProvisionType.ALINEA,
            12,
            "b) os maiores de setenta anos;",
            label="b",
        ),
        label="II",
    )
    paragraph = provision(
        "CF88/ARTICLE:14/PARAGRAPH:1",
        ProvisionType.PARAGRAPH,
        8,
        "§ 1º O alistamento eleitoral e o voto são:",
        provision(
            "CF88/ARTICLE:14/PARAGRAPH:1/INCISO:I",
            ProvisionType.INCISO,
            9,
            "I - obrigatórios para os maiores de dezoito anos;",
            label="I",
        ),
        optional,
        label="1",
    )
    article14 = provision(
        "CF88/ARTICLE:14",
        ProvisionType.ARTICLE,
        7,
        "Art. 14.",
        paragraph,
        label="14",
    )
    article143 = provision(
        "CF88/ARTICLE:143",
        ProvisionType.ARTICLE,
        15,
        "Art. 143. O serviço militar é obrigatório nos termos da lei.",
        label="143",
    )
    political = provision(
        "CF88/TITLE:II/CHAPTER:IV",
        ProvisionType.CHAPTER,
        2,
        "CAPÍTULO IV — Dos Direitos Políticos",
        article5,
        article14,
        label="IV",
    )
    armed = provision(
        "CF88/TITLE:V/CHAPTER:II",
        ProvisionType.CHAPTER,
        14,
        "CAPÍTULO II — Das Forças Armadas",
        article143,
        label="II",
    )
    return ParsedAct(
        "CF88",
        "Constituição da República Federativa do Brasil de 1988",
        "CONSTITUTION",
        (political, armed),
        (
            ParsedMetadata(
                "PROMULGATION",
                "Brasília, 5 de outubro de 1988.",
                "block:20",
                datetime(1988, 10, 5, tzinfo=UTC).date(),
            ),
        ),
        datetime(1988, 10, 5, tzinfo=UTC).date(),
    )


def parsed_article_with_governing_caput() -> ParsedAct:
    article = provision(
        "CF88/ARTICLE:60",
        ProvisionType.ARTICLE,
        1,
        "Art. 60.",
        provision(
            "CF88/ARTICLE:60/CAPUT:@caput",
            ProvisionType.CAPUT,
            2,
            "A Constituição poderá ser emendada mediante proposta de:",
        ),
        provision(
            "CF88/ARTICLE:60/INCISO:I",
            ProvisionType.INCISO,
            3,
            "I - um terço, no mínimo, dos membros da Câmara ou do Senado;",
            label="I",
        ),
        label="60",
    )
    return ParsedAct("CF88", "Constituição Federal", "CONSTITUTION", (article,))


def units():
    act = parsed_cf()
    version_hash = act_version_hash(act.code, "a" * 64, "parser-v2")
    return SearchUnitBuilder().build(act, version_hash)


def unit(anchor: str):
    return next(item for item in units() if item.anchor_stable_key == anchor)


def test_stable_key_and_hash_are_deterministic():
    assert (
        provision_stable_key(
            "CF88", ProvisionType.PARAGRAPH, "Único", "CF88/ARTICLE:11"
        )
        == "CF88/ARTICLE:11/PARAGRAPH:UNICO"
    )
    assert units() == units()
    assert all(len(item.content_hash) == 64 for item in units())


def test_article_14_preserves_electoral_vote_and_optional_context_in_order():
    search_text = unit("CF88/ARTICLE:14").search_text
    assert search_text.index("alistamento eleitoral") < search_text.index(
        "facultativos"
    )
    assert "voto" in search_text
    assert "analfabetos" in search_text
    assert "maiores de setenta anos" in search_text


def test_context_distinguishes_military_and_electoral_enlistment():
    military = unit("CF88/ARTICLE:143").search_text
    electoral = unit("CF88/ARTICLE:14").search_text
    assert "Das Forças Armadas" in military
    assert "serviço militar" in military and "obrigatório" in military
    assert "alistamento eleitoral" in electoral
    assert "alistamento eleitoral" not in military


def test_house_inviolability_context_is_preserved():
    text = unit("CF88/ARTICLE:5/INCISO:XI").search_text
    for expected in (
        "casa",
        "asilo inviolável",
        "consentimento",
        "flagrante delito",
        "desastre",
        "socorro",
        "determinação judicial",
    ):
        assert expected in text


def test_perpetual_penalty_has_parent_context_without_contaminating_citation():
    key = "CF88/ARTICLE:5/INCISO:XLVII/ALINEA:B"
    contextual = unit(key)
    assert "não haverá penas" in contextual.search_text
    assert "de caráter perpétuo" in contextual.search_text
    leaf = parsed_cf().root_provisions[0].children[0].children[1].children[0]
    assert leaf.citation_text == "b) de caráter perpétuo;"
    assert "não haverá penas" not in leaf.citation_text


def test_document_metadata_has_promulgation_and_provenance():
    metadata = next(
        item for item in units() if item.unit_type is SearchUnitType.DOCUMENT_METADATA
    )
    assert "5 de outubro de 1988" in metadata.search_text
    assert metadata.source_locator == "block:20"
    assert metadata.anchor_stable_key is None
    assert metadata.stable_reference == "CF88/METADATA:PROMULGATION_DATE"
    assert "Data de promulgação" in metadata.search_text


def test_contextual_descendant_includes_governing_caput_without_changing_source():
    act = parsed_article_with_governing_caput()
    built = SearchUnitBuilder().build(
        act, act_version_hash(act.code, "a" * 64, "parser-v3")
    )
    inciso = next(
        item for item in built if item.anchor_stable_key == "CF88/ARTICLE:60/INCISO:I"
    )

    assert "A Constituição poderá ser emendada mediante proposta de" in (
        inciso.search_text
    )
    assert inciso.source_excerpt is None
    assert inciso.source_locator == "block:3"
    assert any(
        item.anchor_stable_key == "CF88/ARTICLE:60/CAPUT:@caput" for item in built
    )


def test_exact_article_caput_projection_is_not_indexed_twice():
    article = provision(
        "CF88/ARTICLE:143",
        ProvisionType.ARTICLE,
        1,
        "Art. 143.",
        provision(
            "CF88/ARTICLE:143/CAPUT:@caput",
            ProvisionType.CAPUT,
            2,
            "O serviço militar é obrigatório nos termos da lei.",
        ),
        label="143",
    )
    act = ParsedAct("CF88", "Constituição Federal", "CONSTITUTION", (article,))
    built = SearchUnitBuilder().build(
        act, act_version_hash(act.code, "a" * 64, "parser-v3")
    )

    assert any(item.unit_type is SearchUnitType.ARTICLE for item in built)
    assert not any(
        item.anchor_stable_key == "CF88/ARTICLE:143/CAPUT:@caput" for item in built
    )


def test_search_unit_reference_removes_structural_ancestry_but_keeps_identity():
    assert unit("CF88/ARTICLE:143").stable_reference == "CF88/ARTICLE:143"
    assert (
        unit("CF88/ARTICLE:5/INCISO:XI").stable_reference == "CF88/ARTICLE:5/INCISO:XI"
    )


def test_parser_extracts_two_acts_promulgation_and_local_provenance():
    raw = FIXTURE.read_bytes()
    capture = source_capture(raw)
    parsed = ConstitutionCorpusParser().parse(capture)
    assert parsed.parser_version == PARSER_VERSION
    assert tuple(act.code for act in parsed.acts) == ("CF88", "ADCT")
    assert parsed.acts[0].promulgation_date.isoformat() == "1988-10-05"
    metadata = next(
        item for item in parsed.acts[0].metadata if item.kind == "PROMULGATION"
    )
    assert metadata.source_locator.startswith("block:")


def test_parser_selects_single_current_article_and_preserves_its_subtree():
    parsed = ConstitutionCorpusParser().parse(
        source_capture(HISTORICAL_FIXTURE.read_bytes())
    )
    cf = next(act for act in parsed.acts if act.code == "CF88")
    article_key = "CF88/@root/TITLE:II/CHAPTER:II/ARTICLE:6"
    articles = [
        item
        for item in walk_provisions(cf.root_provisions)
        if item.stable_key == article_key
    ]

    assert len(articles) == 1
    article = articles[0]
    assert article.document_order > 1
    assert article.citation_text == "Art. 6º"
    assert json.loads(article.source_locator or "{}") == {
        "anchors": [],
        "block_index": 11,
        "source_line": 12,
        "tag": "p",
    }
    assert [child.provision_type for child in article.children] == [
        ProvisionType.CAPUT,
        ProvisionType.PARAGRAPH,
    ]
    assert "direitos sociais" in article.children[0].citation_text
    assert "Regra vigente" in article.children[1].citation_text
    validate_unique_provision_keys(parsed)


def test_parser_rejects_two_current_occurrences_with_both_locators():
    raw = HISTORICAL_FIXTURE.read_text().replace(
        "<p><strike>Art. 6&ordm; Reda&ccedil;&atilde;o anterior sem "
        "classifica&ccedil;&atilde;o conclusiva.</strike></p>",
        "<p>Art. 6&ordm; Outra reda&ccedil;&atilde;o marcada como corrente.</p>",
    )
    with pytest.raises(DuplicateProvisionStableKey) as error:
        ConstitutionCorpusParser().parse(source_capture(raw.encode()))

    assert error.value.stable_key.endswith("/ARTICLE:6")
    assert "block_index" in (error.value.first_locator or "")
    assert "block_index" in (error.value.second_locator or "")


def test_use_case_fails_fast_on_duplicate_key_before_repository():
    duplicate = provision(
        "CF88/ARTICLE:6", ProvisionType.ARTICLE, 2, "Art. 6º", label="6"
    )
    parsed = ParsedCorpus(
        (
            ParsedAct(
                "CF88",
                "Constituição",
                "CONSTITUTION",
                (
                    provision(
                        "CF88/ARTICLE:6",
                        ProvisionType.ARTICLE,
                        1,
                        "Art. 6º",
                        label="6",
                    ),
                    duplicate,
                ),
            ),
        ),
        "parser-v2",
    )
    repository = MemoryRepository()
    use_case = BuildCorpusUseCase(
        FakeFetcher(source_capture(FIXTURE.read_bytes())),
        FakeParser(parsed),
        repository,
        SearchUnitBuilder(),
    )

    with pytest.raises(DuplicateProvisionStableKey, match="primeira=block:1"):
        use_case.execute()
    assert repository.snapshots == 0


def source_capture(raw: bytes, suffix: str = "") -> SourceCapture:
    payload = raw + suffix.encode()
    return SourceCapture(
        "Planalto",
        "https://www.planalto.gov.br",
        "https://example.test/constituicao.htm",
        "https://example.test/constituicao.htm",
        datetime.now(UTC),
        payload,
        hashlib.sha256(payload).hexdigest(),
    )


def walk_provisions(provisions: tuple[ParsedProvision, ...]):
    for item in provisions:
        yield item
        yield from walk_provisions(item.children)


@dataclass
class FakeFetcher:
    capture: SourceCapture

    def fetch(self):
        return self.capture


@dataclass
class FakeParser:
    parsed: ParsedCorpus

    def parse(self, capture):
        return self.parsed


class MemoryRepository:
    def __init__(self):
        self.hashes: set[str] = set()
        self.snapshots = 0
        self.versions = 0

    def materialize(self, capture, parsed, search_units):
        created = capture.sha256 not in self.hashes
        if created:
            self.hashes.add(capture.sha256)
            self.snapshots += 1
            self.versions += len(parsed.acts)
        return MaterializedCorpus(
            created,
            capture.sha256,
            len(parsed.acts),
            sum(len(act.root_provisions) for act in parsed.acts),
            sum(len(items) for _, items in search_units),
        )

    def status(self):
        raise NotImplementedError


def test_build_is_idempotent_and_new_snapshot_preserves_old_version():
    raw = FIXTURE.read_bytes()
    parsed = ParsedCorpus(
        (parsed_cf(), ParsedAct("ADCT", "ADCT", "TRANSITIONAL", ())), "parser-v2"
    )
    repository = MemoryRepository()
    first = BuildCorpusUseCase(
        FakeFetcher(source_capture(raw)),
        FakeParser(parsed),
        repository,
        SearchUnitBuilder(),
    )
    assert first.execute().outcome.value == "CREATED"
    assert first.execute().outcome.value == "ALREADY_READY"
    second = BuildCorpusUseCase(
        FakeFetcher(source_capture(raw, "nova versão")),
        FakeParser(parsed),
        repository,
        SearchUnitBuilder(),
    )
    assert second.execute().outcome.value == "CREATED"
    assert repository.snapshots == 2
    assert repository.versions == 4


def test_rematerialization_reads_exact_snapshot_and_never_calls_http(monkeypatch):
    raw = FIXTURE.read_bytes()
    capture = source_capture(raw)
    parsed = ParsedCorpus(
        (parsed_cf(), ParsedAct("ADCT", "ADCT", "TRANSITIONAL", ())),
        "parser-v3",
    )
    reader = FakeSnapshotReader(capture)
    parser = RecordingParser(parsed)
    repository = MemoryRepository()
    http_calls: list[None] = []

    def unexpected_http(_self):
        http_calls.append(None)
        raise AssertionError("rematerialização não pode acessar HTTP")

    monkeypatch.setattr(
        "consultor_juridico.infrastructure.corpus.source."
        "PlanaltoHttpSourceFetcher.fetch",
        unexpected_http,
    )
    use_case = RematerializeCorpusFromSnapshotUseCase(
        reader,
        MaterializeCorpusUseCase(parser, repository, SearchUnitBuilder()),
    )

    result = use_case.execute(capture.sha256)

    assert result.outcome.value == "CREATED"
    assert reader.requested_hashes == [capture.sha256]
    assert parser.received_capture is capture
    assert parser.received_capture.raw_bytes == raw
    assert http_calls == []


@pytest.mark.parametrize(
    "error",
    (
        SourceSnapshotNotFound("f" * 64),
        SourceSnapshotIntegrityError("a" * 64, "b" * 64),
    ),
)
def test_rematerialization_fails_before_parsing_when_snapshot_read_fails(error):
    repository = MemoryRepository()
    parser = RecordingParser(ParsedCorpus((), "parser-v3"))
    use_case = RematerializeCorpusFromSnapshotUseCase(
        FailingSnapshotReader(error),
        MaterializeCorpusUseCase(parser, repository, SearchUnitBuilder()),
    )

    with pytest.raises(type(error)):
        use_case.execute("f" * 64)

    assert parser.received_capture is None
    assert repository.snapshots == 0


@dataclass
class FakeSnapshotReader:
    capture: SourceCapture

    def __post_init__(self):
        self.requested_hashes: list[str] = []

    def read_by_sha256(self, snapshot_sha256):
        self.requested_hashes.append(snapshot_sha256)
        return self.capture


@dataclass
class FailingSnapshotReader:
    error: Exception

    def read_by_sha256(self, snapshot_sha256):
        raise self.error


@dataclass
class RecordingParser:
    parsed: ParsedCorpus

    def __post_init__(self):
        self.received_capture: SourceCapture | None = None

    def parse(self, capture):
        self.received_capture = capture
        return self.parsed
