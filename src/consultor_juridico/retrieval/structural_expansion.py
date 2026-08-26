"""Expansão estrutural offline, limitada a filhos normativos diretos."""

from dataclasses import dataclass

from consultor_juridico.retrieval.types import RetrievalCandidate

ALLOWED_CONTAINERS = frozenset({"SECTION", "SUBSECTION"})
MAX_STRUCTURAL_CHILDREN_PER_PARENT = 8


@dataclass(frozen=True, slots=True)
class StructuralNode:
    candidate: RetrievalCandidate
    legal_version_id: str
    parent_id: str | None
    text_status: str = "CURRENT"
    content_role: str = "NORMATIVE"


@dataclass(frozen=True, slots=True)
class StructuralPromotion:
    candidate: RetrievalCandidate
    retrieval_source: str
    structural_parent_identity: str
    structural_child_identity: str
    parent_original_rank: int
    parent_original_retrieval_channel: str
    expansion_rule: str
    structural_score: float


def expand_direct_children(
    recovered: tuple[StructuralNode, ...],
    nodes: tuple[StructuralNode, ...],
    *,
    top_k: int,
    max_children: int = MAX_STRUCTURAL_CHILDREN_PER_PARENT,
    decay: float = 0.85,
) -> tuple[StructuralPromotion, ...]:
    """Promove somente filhos diretos elegíveis de containers recuperados.

    A função é deliberadamente offline: não calcula score lexical/vectorial,
    não fabrica ranks e não atravessa a árvore recursivamente.
    """
    if top_k < 1 or max_children < 1 or not 0 < decay <= 1:
        raise ValueError("Parâmetros de expansão estrutural inválidos")
    recovered_ids = {node.candidate.legal_element_id for node in recovered}
    promotions: list[StructuralPromotion] = []
    for parent in recovered:
        if parent.candidate.legal_element_id not in recovered_ids:
            continue
        if parent.candidate.element_type not in ALLOWED_CONTAINERS:
            continue
        if (
            parent.candidate.lexical_rank is None
            and parent.candidate.vector_rank is None
        ):
            continue
        parent_rank = min(
            rank
            for rank in (parent.candidate.lexical_rank, parent.candidate.vector_rank)
            if rank is not None
        )
        children = [
            node
            for node in nodes
            if node.parent_id == str(parent.candidate.legal_element_id)
            and node.legal_version_id == parent.legal_version_id
            and node.candidate.legal_act == parent.candidate.legal_act
            and node.candidate.element_type in {"ARTICLE", "CAPUT"}
            and node.text_status == "CURRENT"
            and node.content_role == "NORMATIVE"
            and node.candidate.identity_key != parent.candidate.identity_key
        ]
        if len(children) > max_children:
            continue
        for child in children:
            resolved_child = child
            expansion_rule = "RECOVERED_CONTAINER_DIRECT_NORMATIVE_CHILD"
            if child.candidate.element_type == "ARTICLE":
                caputs = [
                    node
                    for node in nodes
                    if node.parent_id == str(child.candidate.legal_element_id)
                    and node.legal_version_id == child.legal_version_id
                    and node.candidate.legal_act == child.candidate.legal_act
                    and node.candidate.element_type == "CAPUT"
                    and node.text_status == "CURRENT"
                    and node.content_role == "NORMATIVE"
                ]
                if len(caputs) == 1:
                    resolved_child = caputs[0]
                    expansion_rule = "RECOVERED_CONTAINER_ARTICLE_RESOLVED_CAPUT"
            promotions.append(
                StructuralPromotion(
                    candidate=resolved_child.candidate,
                    retrieval_source="STRUCTURAL_EXPANSION",
                    structural_parent_identity=parent.candidate.identity_key,
                    structural_child_identity=resolved_child.candidate.identity_key,
                    parent_original_rank=parent_rank,
                    parent_original_retrieval_channel=_channel(parent.candidate),
                    expansion_rule=expansion_rule,
                    structural_score=float(parent.candidate.rrf_score or 0.0) * decay,
                )
            )
    return tuple(promotions[:top_k])


def _channel(candidate: RetrievalCandidate) -> str:
    channels = []
    if candidate.lexical_rank is not None:
        channels.append("LEXICAL")
    if candidate.vector_rank is not None:
        channels.append("VECTOR")
    return "MULTIPLE" if len(channels) > 1 else (channels[0] if channels else "NONE")
