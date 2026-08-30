"""Testes PostgreSQL do modelo congelado de parsing, sem executar parser."""

import uuid
import warnings
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers

from consultor_juridico.db.session import SessionLocal, engine
from consultor_juridico.models import (
    LegalAct,
    LegalElement,
    LegalProvision,
    LegalVersion,
    ParsingRun,
    Source,
    SourceDocument,
)
from consultor_juridico.services.db_service import run_migrations


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    run_migrations()
    yield


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


def _source_document(session: Session, suffix: str) -> SourceDocument:
    source = Source(name=f"Fonte {suffix}", base_url=f"https://source-{suffix}.example")
    session.add(source)
    session.flush()
    document = SourceDocument(
        source_id=source.id,
        url_source=f"https://source-{suffix}.example/document",
        raw_bytes=f"document-{suffix}".encode(),
        content_hash_sha256=f"hash-{suffix}",
    )
    session.add(document)
    session.flush()
    return document


def _run(
    session: Session,
    document: SourceDocument,
    suffix: str,
    **overrides,
) -> ParsingRun:
    values = {
        "source_document_id": document.id,
        "parser_name": "constitutional_parser",
        "parser_version": suffix,
    }
    values.update(overrides)
    parsing_run = ParsingRun(**values)
    session.add(parsing_run)
    session.flush()
    return parsing_run


def _act(session: Session, suffix: str) -> LegalAct:
    legal_act = LegalAct(
        title=f"Ato {suffix}",
        short_name=f"ACT-{suffix[-36:]}",
        act_type="CONSTITUICAO",
    )
    session.add(legal_act)
    session.flush()
    return legal_act


def _version(
    session: Session,
    document: SourceDocument,
    parsing_run: ParsingRun,
    legal_act: LegalAct,
    suffix: str,
    *,
    active: bool = False,
) -> LegalVersion:
    version = LegalVersion(
        legal_act_id=legal_act.id,
        source_document_id=document.id,
        parsing_run_id=parsing_run.id,
        version_label=f"Version {suffix}",
        is_active_for_query=active,
    )
    session.add(version)
    session.flush()
    return version


def _provision(
    session: Session,
    legal_act: LegalAct,
    element_type: str,
    identity_key: str,
    *,
    parent: LegalProvision | None = None,
    number_label: str | None = None,
) -> LegalProvision:
    provision = LegalProvision(
        legal_act_id=legal_act.id,
        parent_id=parent.id if parent else None,
        element_type=element_type,
        number_label=number_label,
        identity_key=identity_key,
    )
    session.add(provision)
    session.flush()
    return provision


def _root(
    session: Session,
    version: LegalVersion,
    legal_act: LegalAct,
    block_index: int = 0,
):
    root_provision = _provision(
        session, legal_act, "DOCUMENT_ROOT", f"root:{legal_act.id}"
    )
    root = LegalElement(
        legal_version_id=version.id,
        legal_act_id=legal_act.id,
        legal_provision_id=root_provision.id,
        element_type="DOCUMENT_ROOT",
        document_order=1,
        raw_text="Constituição Federal de 1988",
        normalized_text="Constituição Federal de 1988",
        text_status="CURRENT",
        source_locator={"block_index": block_index},
    )
    session.add(root)
    session.flush()
    return root


def _chain(session: Session, suffix: str):
    document = _source_document(session, suffix)
    parsing_run = _run(session, document, suffix)
    legal_act = _act(session, suffix)
    version = _version(session, document, parsing_run, legal_act, suffix)
    root = _root(session, version, legal_act)
    return document, parsing_run, legal_act, version, root


def _valid_child(
    session: Session, version: LegalVersion, root: LegalElement, **overrides
):
    element_type = overrides.get("element_type", "CAPUT")
    legal_provision_id = None
    provision_types = {
        "PREAMBLE",
        "TITLE",
        "CHAPTER",
        "SECTION",
        "SUBSECTION",
        "ARTICLE",
        "CAPUT",
        "PARAGRAPH",
        "INCISO",
        "ALINEA",
        "ITEM",
    }
    numbered_types = {
        "TITLE",
        "CHAPTER",
        "SECTION",
        "SUBSECTION",
        "ARTICLE",
        "PARAGRAPH",
        "INCISO",
        "ALINEA",
        "ITEM",
    }
    if element_type == "DOCUMENT_ROOT":
        legal_provision_id = root.legal_provision_id
    elif element_type in provision_types:
        provision = _provision(
            session,
            version.legal_act,
            element_type,
            f"child:{uuid.uuid4()}",
            parent=root.legal_provision,
            number_label=(
                overrides.get("number_label") or "I"
                if element_type in numbered_types
                else None
            ),
        )
        legal_provision_id = provision.id
    values = {
        "legal_version_id": version.id,
        "legal_act_id": version.legal_act_id,
        "legal_provision_id": legal_provision_id,
        "parent_id": root.id,
        "element_type": "CAPUT",
        "document_order": 2,
        "raw_text": "Texto normativo.",
        "normalized_text": "Texto normativo.",
        "source_locator": {"block_index": 1},
    }
    values.update(overrides)
    return LegalElement(**values)


def test_parsing_run_relationships_and_mappers_have_no_warnings(db_session: Session):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        configure_mappers()
    assert not caught

    document, parsing_run, act, version, _ = _chain(db_session, "relationships")
    assert parsing_run.source_document.id == document.id
    assert version.parsing_run.id == parsing_run.id
    assert parsing_run.legal_versions == [version]
    assert act.versions == [version]


def test_parsing_run_logical_identity_is_unique(db_session: Session):
    document = _source_document(db_session, "run-unique")
    _run(db_session, document, "v1")
    db_session.add(
        ParsingRun(
            source_document_id=document.id,
            parser_name="constitutional_parser",
            parser_version="v1",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("status", ["RUNNING", "COMPLETED", "FAILED"])
def test_parsing_run_accepts_valid_status(db_session: Session, status: str):
    document = _source_document(db_session, f"status-{status}")
    finished_at = None if status == "RUNNING" else datetime.now(UTC)
    parsing_run = _run(
        db_session,
        document,
        status,
        status=status,
        finished_at=finished_at,
    )
    assert parsing_run.status == status


def test_parsing_run_rejects_invalid_status(db_session: Session):
    document = _source_document(db_session, "invalid-status")
    db_session.add(
        ParsingRun(
            source_document_id=document.id,
            parser_name="constitutional_parser",
            parser_version="invalid",
            status="UNKNOWN",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    ("status", "finished_at"),
    [
        ("RUNNING", datetime.now(UTC)),
        ("COMPLETED", None),
        ("FAILED", None),
    ],
)
def test_parsing_run_rejects_inconsistent_timestamps(
    db_session: Session, status: str, finished_at: datetime | None
):
    document = _source_document(db_session, f"timestamp-{status}")
    db_session.add(
        ParsingRun(
            source_document_id=document.id,
            parser_name="constitutional_parser",
            parser_version=status,
            status=status,
            finished_at=finished_at,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_legal_version_rejects_source_document_different_from_run(
    db_session: Session,
):
    document_a = _source_document(db_session, "version-source-a")
    document_b = _source_document(db_session, "version-source-b")
    parsing_run = _run(db_session, document_a, "source-mismatch")
    legal_act = _act(db_session, "source-mismatch")
    db_session.add(
        LegalVersion(
            legal_act_id=legal_act.id,
            source_document_id=document_b.id,
            parsing_run_id=parsing_run.id,
            version_label="Invalid",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_legal_version_rejects_duplicate_act_in_run(db_session: Session):
    document = _source_document(db_session, "version-act-unique")
    parsing_run = _run(db_session, document, "v1")
    legal_act = _act(db_session, "version-act-unique")
    _version(db_session, document, parsing_run, legal_act, "one")
    db_session.add(
        LegalVersion(
            legal_act_id=legal_act.id,
            source_document_id=document.id,
            parsing_run_id=parsing_run.id,
            version_label="Duplicate",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_only_one_active_version_per_legal_act(db_session: Session):
    document = _source_document(db_session, "active-unique")
    legal_act = _act(db_session, "active-unique")
    run_v1 = _run(db_session, document, "v1")
    run_v2 = _run(db_session, document, "v2")
    _version(db_session, document, run_v1, legal_act, "v1", active=True)
    db_session.add(
        LegalVersion(
            legal_act_id=legal_act.id,
            source_document_id=document.id,
            parsing_run_id=run_v2.id,
            version_label="v2",
            is_active_for_query=True,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_inactive_versions_per_legal_act_are_allowed(db_session: Session):
    document = _source_document(db_session, "inactive-many")
    legal_act = _act(db_session, "inactive-many")
    run_v1 = _run(db_session, document, "v1")
    run_v2 = _run(db_session, document, "v2")
    first = _version(db_session, document, run_v1, legal_act, "v1")
    second = _version(db_session, document, run_v2, legal_act, "v2")
    assert first.is_active_for_query is False
    assert second.is_active_for_query is False


def test_legal_element_parent_and_children_relationship(db_session: Session):
    *_, version, root = _chain(db_session, "tree")
    child = _valid_child(db_session, version, root)
    db_session.add(child)
    db_session.flush()
    assert child.parent.id == root.id
    assert child in root.children


def test_legal_element_rejects_parent_from_other_version(db_session: Session):
    document = _source_document(db_session, "cross-parent")
    parsing_run = _run(db_session, document, "v1")
    version_a = _version(
        db_session, document, parsing_run, _act(db_session, "cross-a"), "a"
    )
    version_b = _version(
        db_session, document, parsing_run, _act(db_session, "cross-b"), "b"
    )
    root_a = _root(db_session, version_a, version_a.legal_act, 0)
    root_b = _root(db_session, version_b, version_b.legal_act, 1)
    child = _valid_child(db_session, version_b, root_b)
    child.parent_id = root_a.id
    db_session.add(child)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_legal_element_rejects_duplicate_document_order(db_session: Session):
    *_, version, root = _chain(db_session, "order-duplicate")
    db_session.add_all(
        [
            _valid_child(db_session, version, root),
            _valid_child(
                db_session, version, root, raw_text="Outro", normalized_text="Outro"
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_legal_element_rejects_non_positive_document_order(db_session: Session):
    *_, version, root = _chain(db_session, "order-positive")
    db_session.add(_valid_child(db_session, version, root, document_order=0))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_legal_element_rejects_second_root(db_session: Session):
    *_, version, _ = _chain(db_session, "root-unique")
    db_session.add(
        LegalElement(
            legal_version_id=version.id,
            legal_act_id=version.legal_act_id,
            legal_provision_id=uuid.uuid4(),
            element_type="DOCUMENT_ROOT",
            document_order=1,
            raw_text="ADCT",
            normalized_text="ADCT",
            text_status="CURRENT",
            source_locator={"block_index": 1},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "overrides",
    [
        {"element_type": "DOCUMENT_ROOT", "document_order": 2},
        {"element_type": "DOCUMENT_ROOT", "text_status": "UNRESOLVED"},
        {"element_type": "DOCUMENT_ROOT", "parent_id": uuid.uuid4()},
        {"parent_id": None},
    ],
)
def test_legal_element_rejects_invalid_root_shape(db_session: Session, overrides: dict):
    *_, version, root = _chain(db_session, f"root-shape-{uuid.uuid4()}")
    candidate = _valid_child(
        db_session, version, root, **({"document_order": 3} | overrides)
    )
    db_session.add(candidate)
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "field,value",
    [
        ("element_type", "UNKNOWN"),
        ("text_status", "UNKNOWN"),
        ("content_role", "UNKNOWN"),
    ],
)
def test_legal_element_rejects_invalid_taxonomy(
    db_session: Session, field: str, value: str
):
    *_, version, root = _chain(db_session, f"taxonomy-{field}")
    db_session.add(_valid_child(db_session, version, root, **{field: value}))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_role": "REFERENCE_NOTE", "text_status": "CURRENT"},
        {"content_role": "NORMATIVE", "text_status": "NOT_APPLICABLE"},
        {
            "element_type": "NOTE",
            "content_role": "NORMATIVE",
            "text_status": "CURRENT",
        },
        {
            "element_type": "CAPUT",
            "content_role": "EDITORIAL_NOTE",
            "text_status": "NOT_APPLICABLE",
        },
    ],
)
def test_legal_element_rejects_incompatible_role_status_or_note(
    db_session: Session, overrides: dict
):
    *_, version, root = _chain(db_session, f"role-{uuid.uuid4()}")
    db_session.add(_valid_child(db_session, version, root, **overrides))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_text", "   "),
        ("normalized_text", "   "),
    ],
)
def test_legal_element_rejects_empty_text(db_session: Session, field: str, value: str):
    *_, version, root = _chain(db_session, f"empty-{field}")
    db_session.add(_valid_child(db_session, version, root, **{field: value}))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("source_locator", [[], {}, {"other": 1}, {"block_index": "1"}])
def test_legal_element_rejects_invalid_source_locator(
    db_session: Session, source_locator
):
    *_, version, root = _chain(db_session, f"locator-{uuid.uuid4()}")
    db_session.add(
        _valid_child(db_session, version, root, source_locator=source_locator)
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_legal_element_rejects_non_object_parser_metadata(db_session: Session):
    *_, version, root = _chain(db_session, "parser-metadata")
    db_session.add(_valid_child(db_session, version, root, parser_metadata=[]))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "element_type",
    [
        "TITLE",
        "CHAPTER",
        "SECTION",
        "SUBSECTION",
        "ARTICLE",
        "PARAGRAPH",
        "INCISO",
        "ALINEA",
        "ITEM",
    ],
)
def test_numbered_legal_elements_require_label(db_session: Session, element_type: str):
    *_, version, root = _chain(db_session, f"label-{element_type}")
    db_session.add(
        _valid_child(
            db_session, version, root, element_type=element_type, number_label=None
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_note_with_editorial_role_is_valid(db_session: Session):
    *_, version, root = _chain(db_session, "valid-note")
    note = _valid_child(
        db_session,
        version,
        root,
        element_type="NOTE",
        content_role="EDITORIAL_NOTE",
        text_status="NOT_APPLICABLE",
        parser_metadata={"links": []},
    )
    db_session.add(note)
    db_session.flush()
    assert db_session.scalar(select(LegalElement).where(LegalElement.id == note.id))


def test_legal_provision_relationships(db_session: Session):
    *_, legal_act, version, root = _chain(db_session, "provision-relationships")
    child = _valid_child(db_session, version, root)
    db_session.add(child)
    db_session.flush()

    assert root.legal_provision in legal_act.provisions
    assert child.legal_provision.parent == root.legal_provision
    assert child.legal_provision in root.legal_provision.children
    assert child in child.legal_provision.occurrences


def test_legal_provision_identity_is_unique_per_act(db_session: Session):
    legal_act = _act(db_session, "provision-key")
    _provision(db_session, legal_act, "DOCUMENT_ROOT", "cf88")
    db_session.add(
        LegalProvision(
            legal_act_id=legal_act.id,
            element_type="DOCUMENT_ROOT",
            identity_key="cf88",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_provision_identity_is_allowed_in_different_acts(db_session: Session):
    first = _act(db_session, "provision-key-a")
    second = _act(db_session, "provision-key-b")
    _provision(db_session, first, "DOCUMENT_ROOT", "root")
    other = _provision(db_session, second, "DOCUMENT_ROOT", "root")
    assert other.legal_act_id == second.id


def test_legal_provision_rejects_parent_from_other_act(db_session: Session):
    first = _act(db_session, "provision-parent-a")
    second = _act(db_session, "provision-parent-b")
    root = _provision(db_session, first, "DOCUMENT_ROOT", "root-a")
    db_session.add(
        LegalProvision(
            legal_act_id=second.id,
            parent_id=root.id,
            element_type="CAPUT",
            identity_key="invalid-parent",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "overrides",
    [
        {"element_type": "NOTE", "identity_key": "note"},
        {"element_type": "UNKNOWN", "identity_key": "unknown"},
        {"element_type": "ARTICLE", "identity_key": "article", "number_label": None},
        {"element_type": "CAPUT", "identity_key": "   "},
    ],
)
def test_legal_provision_rejects_invalid_shape(db_session: Session, overrides: dict):
    legal_act = _act(db_session, f"provision-shape-{uuid.uuid4()}")
    root = _provision(db_session, legal_act, "DOCUMENT_ROOT", "root")
    values = {
        "legal_act_id": legal_act.id,
        "parent_id": root.id,
        "element_type": "CAPUT",
        "identity_key": "caput",
    }
    values.update(overrides)
    db_session.add(LegalProvision(**values))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_occurrence_rejects_provision_from_other_act(db_session: Session):
    *_, version, root = _chain(db_session, "occurrence-cross-act")
    other_act = _act(db_session, "occurrence-other-act")
    other_root = _provision(db_session, other_act, "DOCUMENT_ROOT", "other-root")
    other_caput = _provision(
        db_session, other_act, "CAPUT", "other-caput", parent=other_root
    )
    candidate = _valid_child(db_session, version, root)
    candidate.legal_provision_id = other_caput.id
    db_session.add(candidate)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_occurrence_rejects_provision_of_other_type(db_session: Session):
    *_, version, root = _chain(db_session, "occurrence-type")
    candidate = _valid_child(db_session, version, root)
    candidate.legal_provision_id = root.legal_provision_id
    db_session.add(candidate)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_normative_occurrence_requires_provision(db_session: Session):
    *_, version, root = _chain(db_session, "occurrence-presence")
    candidate = _valid_child(db_session, version, root)
    candidate.legal_provision_id = None
    db_session.add(candidate)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_note_rejects_provision(db_session: Session):
    *_, version, root = _chain(db_session, "note-provision")
    note = _valid_child(
        db_session,
        version,
        root,
        element_type="NOTE",
        content_role="EDITORIAL_NOTE",
        text_status="NOT_APPLICABLE",
    )
    note.legal_provision_id = root.legal_provision_id
    db_session.add(note)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_only_one_current_occurrence_per_version_provision(db_session: Session):
    *_, version, root = _chain(db_session, "current-occurrence")
    first = _valid_child(db_session, version, root, text_status="CURRENT")
    db_session.add(first)
    db_session.flush()
    duplicate = LegalElement(
        legal_version_id=version.id,
        legal_act_id=version.legal_act_id,
        legal_provision_id=first.legal_provision_id,
        parent_id=root.id,
        element_type="CAPUT",
        document_order=3,
        raw_text="Nova ocorrência corrente",
        normalized_text="Nova ocorrência corrente",
        text_status="CURRENT",
        source_locator={"block_index": 2},
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_historical_occurrences_per_provision_are_allowed(
    db_session: Session,
):
    *_, version, root = _chain(db_session, "historical-occurrences")
    first = _valid_child(db_session, version, root, text_status="HISTORICAL")
    db_session.add(first)
    db_session.flush()
    second = LegalElement(
        legal_version_id=version.id,
        legal_act_id=version.legal_act_id,
        legal_provision_id=first.legal_provision_id,
        parent_id=root.id,
        element_type="CAPUT",
        document_order=3,
        raw_text="Redação histórica anterior",
        normalized_text="Redação histórica anterior",
        text_status="HISTORICAL",
        source_locator={"block_index": 2},
    )
    db_session.add(second)
    db_session.flush()
    assert second.legal_provision_id == first.legal_provision_id
