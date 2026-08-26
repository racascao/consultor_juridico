from uuid import uuid4

from consultor_juridico.retrieval.structural_expansion import (
    StructuralNode,
    expand_direct_children,
)
from consultor_juridico.retrieval.types import RetrievalCandidate


def node(
    identity,
    typ,
    *,
    parent=None,
    act="CF",
    version="V",
    status="CURRENT",
    role="NORMATIVE",
    rank=1,
):
    candidate = RetrievalCandidate(
        uuid4(),
        uuid4(),
        uuid4(),
        act,
        typ,
        None,
        identity,
        identity,
        lexical_rank=rank,
        rrf_score=0.5,
    )
    return StructuralNode(candidate, version, parent, status, role)


def test_section_promotes_only_direct_normative_child_with_provenance():
    parent = node("CF/SECTION:I", "SECTION")
    child = node(
        "CF/SECTION:I/ARTICLE:137",
        "ARTICLE",
        parent=str(parent.candidate.legal_element_id),
    )
    result = expand_direct_children((parent,), (parent, child), top_k=10)
    assert len(result) == 1
    assert result[0].retrieval_source == "STRUCTURAL_EXPANSION"
    assert result[0].structural_parent_identity == parent.candidate.identity_key
    assert result[0].candidate.lexical_rank == 1


def test_sibling_cross_scope_and_invalid_children_are_rejected():
    parent = node("CF/SECTION:I", "SECTION")
    sibling = node(
        "CF/SECTION:II/ARTICLE:1",
        "ARTICLE",
        parent=str(uuid4()),
    )
    wrong_version = node(
        "CF/SECTION:I/ARTICLE:2",
        "ARTICLE",
        parent=str(parent.candidate.legal_element_id),
        version="W",
    )
    note = node(
        "CF/SECTION:I/NOTE",
        "NOTE",
        parent=str(parent.candidate.legal_element_id),
        role="EDITORIAL_NOTE",
    )
    assert (
        expand_direct_children(
            (parent,), (parent, sibling, wrong_version, note), top_k=10
        )
        == ()
    )


def test_unretrieved_weak_and_oversized_containers_fail_closed():
    weak = node("CF/SECTION:I", "SECTION", rank=None)
    weak = StructuralNode(weak.candidate, weak.legal_version_id, weak.parent_id)
    assert expand_direct_children((weak,), (weak,), top_k=10) == ()
