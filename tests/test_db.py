"""Testes de banco de dados, migrations, integridade e relacionamentos do modelo."""

import uuid

import pytest
from alembic import command
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from consultor_juridico.db.session import SessionLocal, engine
from consultor_juridico.models import (
    Chunk,
    ChunkLegalElement,
    Citation,
    Claim,
    Embedding,
    EvidenceItem,
    EvidenceSet,
    LegalAct,
    LegalElement,
    LegalVersion,
    ParsingRun,
    Source,
    SourceDocument,
)
from consultor_juridico.services.db_service import (
    check_db_status,
    get_alembic_config,
    run_migrations,
)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Garante que as migrations foram aplicadas no banco antes de rodar os testes."""
    run_migrations()
    yield


@pytest.fixture
def db_session() -> Session:
    """Retorna uma sessão do banco limpa com rollback automático após o teste."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Helpers de fixture para criação de objetos reutilizáveis nos testes
# ---------------------------------------------------------------------------


def _create_legal_chain(
    db_session: Session, suffix: str
) -> tuple[Source, SourceDocument, LegalAct, LegalVersion, LegalElement, Chunk]:
    """Cria a cadeia mínima Source → SourceDocument → LegalAct → LegalVersion →
    LegalElement → Chunk para ser usada nos testes."""
    source = Source(name=f"Planalto_{suffix}", base_url="http://planalto.gov.br")
    db_session.add(source)
    db_session.flush()

    source_doc = SourceDocument(
        source_id=source.id,
        url_source=f"http://planalto.gov.br/cf88_{suffix}.htm",
        raw_bytes=f"<html>CF88 {suffix}</html>".encode(),
        content_hash_sha256=f"hash_cf88_{suffix}",
    )
    db_session.add(source_doc)
    db_session.flush()

    legal_act = LegalAct(
        title="Constituição Federal de 1988",
        short_name=f"CF/88_{suffix}",
        act_type="CONSTITUICAO",
    )
    db_session.add(legal_act)
    db_session.flush()

    parsing_run = ParsingRun(
        source_document_id=source_doc.id,
        parser_name="test_parser",
        parser_version=suffix,
    )
    db_session.add(parsing_run)
    db_session.flush()

    legal_version = LegalVersion(
        legal_act_id=legal_act.id,
        source_document_id=source_doc.id,
        parsing_run_id=parsing_run.id,
        version_label=f"Compilada 2026 {suffix}",
    )
    db_session.add(legal_version)
    db_session.flush()

    root = LegalElement(
        legal_version_id=legal_version.id,
        element_type="DOCUMENT_ROOT",
        document_order=1,
        raw_text="Constituição Federal de 1988",
        normalized_text="Constituição Federal de 1988",
        text_status="CURRENT",
        source_locator={"block_index": 0},
    )
    db_session.add(root)
    db_session.flush()

    elem = LegalElement(
        legal_version_id=legal_version.id,
        parent_id=root.id,
        element_type="ARTICLE",
        number_label="Art. 5º",
        document_order=2,
        raw_text="Art. 5º",
        normalized_text="Art. 5º",
        source_locator={"block_index": 1},
        path=f"/art-5-{suffix}",
    )
    db_session.add(elem)
    db_session.flush()

    chunk = Chunk(
        legal_version_id=legal_version.id,
        chunk_text=f"Texto do chunk {suffix}",
    )
    db_session.add(chunk)
    db_session.flush()

    return source, source_doc, legal_act, legal_version, elem, chunk


# ---------------------------------------------------------------------------
# Testes de infraestrutura: conexão e status
# ---------------------------------------------------------------------------


def test_db_connection_and_status():
    """Testa a conexão e o status do banco via db_service."""
    status = check_db_status()
    assert status["connected"] is True
    assert "alembic_version" in status["tables"]
    assert "sources" in status["tables"]
    assert "legal_elements" in status["tables"]
    assert "embeddings" in status["tables"]


def test_alembic_migration_and_rollback():
    """Testa o ciclo apenas em banco vazio e nunca desmonta capturas reais."""
    config = get_alembic_config()

    with SessionLocal() as session:
        document_count = session.scalar(
            select(func.count()).select_from(SourceDocument)
        )
    if document_count:
        status = check_db_status()
        assert status["alembic_version"] == "004_frozen_parsing_model"
        return

    # Downgrade to base
    command.downgrade(config, "base")
    status_down = check_db_status()
    assert status_down["connected"] is True
    assert "sources" not in status_down["tables"]

    # Re-apply upgrade
    command.upgrade(config, "head")
    status_up = check_db_status()
    assert status_up["connected"] is True
    assert "sources" in status_up["tables"]
    assert status_up["alembic_version"] == "004_frozen_parsing_model"


def test_source_base_url_is_unique(db_session: Session):
    """A base_url identifica fisicamente uma Source."""
    db_session.add_all(
        [
            Source(name="Planalto A", base_url="https://www.planalto.gov.br"),
            Source(name="Planalto B", base_url="https://www.planalto.gov.br"),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_source_document_hash_is_unique_per_source(db_session: Session):
    """O mesmo hash pode existir em fontes distintas, mas não na mesma fonte."""
    source_a = Source(name="Fonte A", base_url="https://a.example")
    source_b = Source(name="Fonte B", base_url="https://b.example")
    db_session.add_all([source_a, source_b])
    db_session.flush()

    db_session.add_all(
        [
            SourceDocument(
                source_id=source_a.id,
                url_source="https://a.example/doc",
                raw_bytes=b"\x00\xffpayload",
                content_hash_sha256="same-hash",
            ),
            SourceDocument(
                source_id=source_b.id,
                url_source="https://b.example/doc",
                raw_bytes=b"\x00\xffpayload",
                content_hash_sha256="same-hash",
            ),
        ]
    )
    db_session.commit()

    duplicate = SourceDocument(
        source_id=source_a.id,
        url_source="https://a.example/other",
        raw_bytes=b"\x00\xffpayload",
        content_hash_sha256="same-hash",
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# Testes de integridade referencial
# ---------------------------------------------------------------------------


def test_foreign_key_integrity_invalid_source(db_session: Session):
    """Verifica se criar SourceDocument sem Source dispara erro de integridade."""
    invalid_doc = SourceDocument(
        source_id=uuid.uuid4(),
        url_source="http://invalid.com",
        raw_bytes=b"<html></html>",
        content_hash_sha256="fakehash123",
    )
    db_session.add(invalid_doc)
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# Testes de hierarquia jurídica
# ---------------------------------------------------------------------------


def test_legal_element_parent_child_hierarchy(db_session: Session):
    """Testa o auto-referenciamento em LegalElement (parent -> child) e navegação."""
    *_, legal_version, _, _ = _create_legal_chain(db_session, "hier")
    root = db_session.scalar(
        select(LegalElement).where(
            LegalElement.legal_version_id == legal_version.id,
            LegalElement.element_type == "DOCUMENT_ROOT",
        )
    )
    assert root is not None

    art5 = LegalElement(
        legal_version_id=legal_version.id,
        parent_id=root.id,
        element_type="ARTICLE",
        number_label="Art. 5º",
        document_order=3,
        raw_text="Art. 5º",
        normalized_text="Art. 5º",
        source_locator={"block_index": 2},
        path="/art-5",
    )
    db_session.add(art5)
    db_session.flush()

    inc1 = LegalElement(
        legal_version_id=legal_version.id,
        parent_id=art5.id,
        element_type="INCISO",
        number_label="I",
        document_order=4,
        raw_text="I - homens e mulheres são iguais em direitos e obrigações...",
        normalized_text="I - homens e mulheres são iguais em direitos e obrigações...",
        source_locator={"block_index": 3},
        path="/art-5/inc-1",
    )
    db_session.add(inc1)
    db_session.commit()

    fetched_art5 = db_session.query(LegalElement).filter_by(id=art5.id).one()
    # Filtra filhos criados neste teste (exclui o criado no helper)
    children = [c for c in fetched_art5.children if c.id == inc1.id]
    assert len(children) == 1
    assert children[0].number_label == "I"

    fetched_inc1 = db_session.query(LegalElement).filter_by(id=inc1.id).one()
    assert fetched_inc1.parent is not None
    assert fetched_inc1.parent.id == art5.id


def test_legal_element_no_self_parent_constraint(db_session: Session):
    """Testa a CheckConstraint que impede um LegalElement de ser pai de si mesmo."""
    *_, legal_version, _, _ = _create_legal_chain(db_session, "self_parent")
    elem_id = uuid.uuid4()
    elem = LegalElement(
        id=elem_id,
        legal_version_id=legal_version.id,
        parent_id=elem_id,  # Autoreferência inválida
        element_type="ARTICLE",
        number_label="Art. 99",
        document_order=3,
        raw_text="Art. 99",
        normalized_text="Art. 99",
        source_locator={"block_index": 2},
    )
    db_session.add(elem)
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# Testes de Chunks e relacionamentos N:N
# ---------------------------------------------------------------------------


def test_chunk_legal_element_many_to_many(db_session: Session):
    """Testa o relacionamento N:N entre Chunk e LegalElement via ChunkLegalElement."""
    *_, legal_version, existing_elem, _ = _create_legal_chain(db_session, "chunk_nn")

    elem1 = LegalElement(
        legal_version_id=legal_version.id,
        parent_id=existing_elem.id,
        element_type="CAPUT",
        document_order=3,
        raw_text="A República Federativa do Brasil...",
        normalized_text="A República Federativa do Brasil...",
        source_locator={"block_index": 2},
    )
    elem2 = LegalElement(
        legal_version_id=legal_version.id,
        parent_id=existing_elem.id,
        element_type="INCISO",
        number_label="I",
        document_order=4,
        raw_text="I - soberania",
        normalized_text="I - soberania",
        source_locator={"block_index": 3},
    )
    db_session.add_all([elem1, elem2])
    db_session.flush()

    chunk = Chunk(
        legal_version_id=legal_version.id,
        chunk_text="Art. 1º A República Federativa... I - soberania;",
        strategy_name="article_with_incisos",
    )
    db_session.add(chunk)
    db_session.flush()

    link1 = ChunkLegalElement(
        chunk_id=chunk.id, legal_element_id=elem1.id, is_primary=True
    )
    link2 = ChunkLegalElement(
        chunk_id=chunk.id, legal_element_id=elem2.id, is_primary=False
    )
    db_session.add_all([link1, link2])
    db_session.commit()

    fetched_chunk = db_session.query(Chunk).filter_by(id=chunk.id).one()
    assert len(fetched_chunk.element_links) == 2
    linked_elem_ids = [link.legal_element_id for link in fetched_chunk.element_links]
    assert elem1.id in linked_elem_ids
    assert elem2.id in linked_elem_ids


# ---------------------------------------------------------------------------
# Testes de Embeddings
# ---------------------------------------------------------------------------


def test_multiple_embeddings_per_chunk(db_session: Session):
    """Testa múltiplos embeddings de modelos diferentes para o mesmo Chunk.

    O banco deve aceitar múltiplas linhas em embeddings para o mesmo chunk_id,
    desde que (chunk_id, provider_name, model_name, model_version) seja único.
    """
    *_, _, _, chunk = _create_legal_chain(db_session, "emb_multi")

    emb_a = Embedding(
        chunk_id=chunk.id,
        provider_name="ollama",
        model_name="nomic-embed-text",
        model_version="v1.5",
        dimensions=3,
        vector=[0.1, 0.2, 0.3],
    )
    emb_b = Embedding(
        chunk_id=chunk.id,
        provider_name="ollama",
        model_name="bge-m3",
        model_version="v1.0",
        dimensions=4,
        vector=[0.4, 0.5, 0.6, 0.7],
    )
    db_session.add_all([emb_a, emb_b])
    db_session.commit()

    fetched_chunk = db_session.query(Chunk).filter_by(id=chunk.id).one()
    assert len(fetched_chunk.embeddings) == 2
    models = {e.model_name for e in fetched_chunk.embeddings}
    assert models == {"nomic-embed-text", "bge-m3"}


def test_unique_embedding_per_chunk_provider_model_version(db_session: Session):
    """Testa que duplicar embedding do mesmo (chunk, provider, model, version) falha.

    A constraint uq_embeddings_chunk_provider_model_version deve rejeitar o duplicado.
    """
    *_, _, _, chunk = _create_legal_chain(db_session, "emb_dup")

    emb1 = Embedding(
        chunk_id=chunk.id,
        provider_name="ollama",
        model_name="nomic",
        model_version="v1",
        dimensions=3,
        vector=[0.1, 0.2, 0.3],
    )
    emb2 = Embedding(
        chunk_id=chunk.id,
        provider_name="ollama",
        model_name="nomic",
        model_version="v1",  # Mesma combinação: deve falhar
        dimensions=3,
        vector=[0.4, 0.5, 0.6],
    )
    db_session.add_all([emb1, emb2])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_different_provider_same_model_allowed(db_session: Session):
    """Testa que o mesmo modelo de nome mas provedor diferente é permitido."""
    *_, _, _, chunk = _create_legal_chain(db_session, "emb_prov")

    emb1 = Embedding(
        chunk_id=chunk.id,
        provider_name="ollama",
        model_name="my-model",
        model_version="v1",
        dimensions=3,
        vector=[0.1, 0.2, 0.3],
    )
    emb2 = Embedding(
        chunk_id=chunk.id,
        provider_name="huggingface",  # Provedor diferente
        model_name="my-model",
        model_version="v1",
        dimensions=3,
        vector=[0.4, 0.5, 0.6],
    )
    db_session.add_all([emb1, emb2])
    db_session.commit()  # Deve aceitar pois o provedor é diferente

    fetched = db_session.query(Chunk).filter_by(id=chunk.id).one()
    assert len(fetched.embeddings) == 2


def test_embedding_vector_dimensions_mismatch_rejected(db_session: Session):
    """Testa que inserir embedding com dimensions incorreta é rejeitado pelo banco.

    A constraint ck_embeddings_vector_dimensions_match garante que
    vector IS NULL OR dimensions = vector_dims(vector).
    """
    *_, _, _, chunk = _create_legal_chain(db_session, "emb_dim")

    emb = Embedding(
        chunk_id=chunk.id,
        provider_name="ollama",
        model_name="test-model",
        model_version="v1",
        dimensions=768,  # Incorreto: vetor tem apenas 3 dimensões
        vector=[0.1, 0.2, 0.3],
    )
    db_session.add(emb)
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# Testes de EvidenceSet e EvidenceItem
# ---------------------------------------------------------------------------


def test_evidence_set_and_evidence_item_snapshot(db_session: Session):
    """Testa o relacionamento EvidenceSet -> EvidenceItem e o snapshot de texto."""
    *_, _, elem, chunk = _create_legal_chain(db_session, "evid")

    evidence_set = EvidenceSet(
        query_text="Quais os direitos fundamentais?",
        retrieval_strategy="hybrid_rrf_v1",
        validation_status="VALIDATED",
        total_items=1,
    )
    db_session.add(evidence_set)
    db_session.flush()

    evidence_item = EvidenceItem(
        evidence_set_id=evidence_set.id,
        chunk_id=chunk.id,
        legal_element_id=elem.id,
        evidence_code="EV-001",
        citation_label="Art. 5º da CF/88",
        text_snapshot="Snapshot congelado do texto no momento da consulta",
        is_validated=True,
    )
    db_session.add(evidence_item)
    db_session.commit()

    fetched_item = db_session.query(EvidenceItem).filter_by(id=evidence_item.id).one()
    assert (
        fetched_item.text_snapshot
        == "Snapshot congelado do texto no momento da consulta"
    )
    assert fetched_item.evidence_set.query_text == "Quais os direitos fundamentais?"


# ---------------------------------------------------------------------------
# Testes de Claim e Citation
# ---------------------------------------------------------------------------


def test_claim_citation_evidence_relationship(db_session: Session):
    """Testa a relação M:N entre Claim, Citation e EvidenceItem."""
    *_, legal_version, elem1, chunk = _create_legal_chain(db_session, "claim")

    elem2 = LegalElement(
        legal_version_id=legal_version.id,
        parent_id=elem1.id,
        element_type="INCISO",
        number_label="LVI",
        document_order=3,
        raw_text="Provas ilícitas",
        normalized_text="Provas ilícitas",
        source_locator={"block_index": 2},
    )
    db_session.add(elem2)
    db_session.flush()

    ev_set = EvidenceSet(
        query_text="Direitos de defesa",
        retrieval_strategy="hybrid_rrf_v1",
        validation_status="VALIDATED",
    )
    db_session.add(ev_set)
    db_session.flush()

    ev_item1 = EvidenceItem(
        evidence_set_id=ev_set.id,
        chunk_id=chunk.id,
        legal_element_id=elem1.id,
        evidence_code="EV-001",
        citation_label="Art. 5, LVII",
        text_snapshot="LVII",
    )
    ev_item2 = EvidenceItem(
        evidence_set_id=ev_set.id,
        chunk_id=chunk.id,
        legal_element_id=elem2.id,
        evidence_code="EV-002",
        citation_label="Art. 5, LVI",
        text_snapshot="LVI",
    )
    db_session.add_all([ev_item1, ev_item2])
    db_session.flush()

    claim_a = Claim(
        claim_code="C1",
        text="Ninguém é culpado antes do trânsito em julgado.",
    )
    claim_b = Claim(
        claim_code="C2",
        text="A presunção de inocência vigora até o trânsito em julgado.",
    )
    db_session.add_all([claim_a, claim_b])
    db_session.flush()

    cit1 = Citation(
        claim_id=claim_a.id, evidence_item_id=ev_item1.id, evidence_set_id=ev_set.id
    )
    cit2 = Citation(
        claim_id=claim_a.id, evidence_item_id=ev_item2.id, evidence_set_id=ev_set.id
    )
    cit3 = Citation(
        claim_id=claim_b.id, evidence_item_id=ev_item1.id, evidence_set_id=ev_set.id
    )
    db_session.add_all([cit1, cit2, cit3])
    db_session.commit()

    fetched_claim_a = db_session.query(Claim).filter_by(id=claim_a.id).one()
    assert len(fetched_claim_a.citations) == 2

    fetched_ev1 = db_session.query(EvidenceItem).filter_by(id=ev_item1.id).one()
    assert len(fetched_ev1.citations) == 2


def test_citation_cross_evidence_set_rejected(db_session: Session):
    """Testa que Citation apontando para EvidenceItem de outro EvidenceSet é rejeitada.

    A FK composta fk_citations_evidence_item_set_composite garante fisicamente
    que evidence_item_id e evidence_set_id registrados na Citation correspondam
    ao mesmo EvidenceSet ao qual o EvidenceItem pertence.

    Cenário:
        EvidenceSet A contém EvidenceItem 1
        EvidenceSet B é outro conjunto distinto

        Tentativa de criar Citation com:
            evidence_item_id = EvidenceItem 1 (pertence ao Set A)
            evidence_set_id  = EvidenceSet B  (Set diferente)

        Deve ser REJEITADA pelo PostgreSQL com IntegrityError.
    """
    *_, _, elem, chunk = _create_legal_chain(db_session, "cross")

    # EvidenceSet A: contém EvidenceItem 1
    ev_set_a = EvidenceSet(
        query_text="Consulta A",
        retrieval_strategy="hybrid_rrf_v1",
        validation_status="VALIDATED",
    )
    db_session.add(ev_set_a)
    db_session.flush()

    ev_item_from_a = EvidenceItem(
        evidence_set_id=ev_set_a.id,
        chunk_id=chunk.id,
        legal_element_id=elem.id,
        evidence_code="EV-001",
        citation_label="Art. 5",
        text_snapshot="Texto A",
    )
    db_session.add(ev_item_from_a)
    db_session.flush()

    # EvidenceSet B: conjunto completamente distinto
    ev_set_b = EvidenceSet(
        query_text="Consulta B",
        retrieval_strategy="hybrid_rrf_v1",
        validation_status="VALIDATED",
    )
    db_session.add(ev_set_b)
    db_session.flush()

    claim = Claim(claim_code="CX", text="Claim com citação cruzada inválida")
    db_session.add(claim)
    db_session.flush()

    # Tentativa de citar EvidenceItem do Set A mas registrar Set B
    cross_citation = Citation(
        claim_id=claim.id,
        evidence_item_id=ev_item_from_a.id,  # pertence ao Set A
        evidence_set_id=ev_set_b.id,  # mas registra Set B → INVÁLIDO
    )
    db_session.add(cross_citation)

    with pytest.raises(IntegrityError):
        db_session.commit()
