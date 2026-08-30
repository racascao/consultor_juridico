"""Construção determinística de representações voltadas ao retrieval."""

from dataclasses import dataclass

from consultor_juridico.domain import (
    ParsedAct,
    ParsedProvision,
    ProvisionType,
    SearchUnitDraft,
    SearchUnitType,
    search_unit_hash,
)

STRUCTURAL_TYPES = {
    ProvisionType.TITLE,
    ProvisionType.CHAPTER,
    ProvisionType.SECTION,
    ProvisionType.SUBSECTION,
}
CONTEXTUAL_TYPES = {
    ProvisionType.CAPUT,
    ProvisionType.PARAGRAPH,
    ProvisionType.INCISO,
    ProvisionType.ALINEA,
    ProvisionType.ITEM,
}
METADATA_RETRIEVAL_LABELS = {
    "DOCUMENT_IDENTIFICATION": "Identificação do documento",
    "PREAMBLE": "Preâmbulo",
    "PROMULGATION": "Data de promulgação",
}


@dataclass(frozen=True, slots=True)
class _LocatedProvision:
    provision: ParsedProvision
    ancestors: tuple[ParsedProvision, ...]


class SearchUnitBuilder:
    """Produz SearchUnits sem persistência, interpretação ou I/O."""

    def build(self, act: ParsedAct, version_hash: str) -> tuple[SearchUnitDraft, ...]:
        located = tuple(self._walk(act.root_provisions))
        units = list(self._metadata_units(act, version_hash))
        article_units: dict[str, SearchUnitDraft] = {}
        for item in located:
            if item.provision.provision_type is ProvisionType.ARTICLE:
                article_unit = self._article_unit(act, version_hash, item)
                article_units[item.provision.stable_key] = article_unit
                units.append(article_unit)
            elif item.provision.provision_type in CONTEXTUAL_TYPES:
                contextual_unit = self._contextual_unit(act, version_hash, item)
                article = self._article_ancestor(item.ancestors)
                if (
                    item.provision.provision_type is ProvisionType.CAPUT
                    and article is not None
                    and article_units[article.stable_key].search_text
                    == contextual_unit.search_text
                ):
                    continue
                units.append(contextual_unit)
        return tuple(
            SearchUnitDraft(
                unit_type=unit.unit_type,
                stable_reference=unit.stable_reference,
                anchor_stable_key=unit.anchor_stable_key,
                search_text=unit.search_text,
                content_hash=unit.content_hash,
                document_order=index,
                provision_stable_keys=unit.provision_stable_keys,
                source_locator=unit.source_locator,
                source_excerpt=unit.source_excerpt,
            )
            for index, unit in enumerate(units, start=1)
        )

    def _metadata_units(
        self, act: ParsedAct, version_hash: str
    ) -> tuple[SearchUnitDraft, ...]:
        return tuple(
            self._draft(
                SearchUnitType.DOCUMENT_METADATA,
                act,
                version_hash,
                None,
                _metadata_reference(act.code, metadata.kind),
                self._metadata_search_text(act, metadata.kind, metadata.citation_text),
                (),
                metadata.source_locator,
                metadata.citation_text,
            )
            for metadata in act.metadata
        )

    def _article_unit(
        self, act: ParsedAct, version_hash: str, item: _LocatedProvision
    ) -> SearchUnitDraft:
        subtree = tuple(self._walk((item.provision,), item.ancestors))
        provisions = tuple(entry.provision for entry in subtree)
        context = self._structural_context(item.ancestors)
        text = self._join(act, (*context, *provisions))
        return self._draft(
            SearchUnitType.ARTICLE,
            act,
            version_hash,
            item.provision.stable_key,
            _stable_reference(act.code, item.provision.stable_key),
            text,
            tuple(entry.stable_key for entry in provisions),
            item.provision.source_locator,
        )

    def _contextual_unit(
        self, act: ParsedAct, version_hash: str, item: _LocatedProvision
    ) -> SearchUnitDraft:
        structural = self._structural_context(item.ancestors)
        article_path = self._context_path(item.ancestors)
        own_subtree = tuple(entry.provision for entry in self._walk((item.provision,)))
        included = _unique_provisions((*structural, *article_path, *own_subtree))
        text = self._join(act, included)
        return self._draft(
            SearchUnitType.CONTEXTUAL_PROVISION,
            act,
            version_hash,
            item.provision.stable_key,
            _stable_reference(act.code, item.provision.stable_key),
            text,
            tuple(entry.stable_key for entry in included),
            item.provision.source_locator,
        )

    def _draft(
        self,
        unit_type: SearchUnitType,
        act: ParsedAct,
        version_hash: str,
        anchor: str | None,
        stable_reference: str,
        text: str,
        provision_keys: tuple[str, ...],
        locator: str | None,
        excerpt: str | None = None,
    ) -> SearchUnitDraft:
        return SearchUnitDraft(
            unit_type=unit_type,
            stable_reference=stable_reference,
            anchor_stable_key=anchor,
            search_text=text,
            content_hash=search_unit_hash(
                unit_type=unit_type,
                act_code=act.code,
                version_hash=version_hash,
                anchor_stable_key=anchor,
                search_text=text,
            ),
            document_order=1,
            provision_stable_keys=provision_keys,
            source_locator=locator,
            source_excerpt=excerpt,
        )

    @staticmethod
    def _join(act: ParsedAct, provisions: tuple[ParsedProvision, ...]) -> str:
        lines = [act.code, act.title]
        lines.extend(
            item.citation_text.strip()
            for item in provisions
            if item.citation_text.strip()
        )
        return "\n".join(lines)

    @staticmethod
    def _structural_context(
        ancestors: tuple[ParsedProvision, ...],
    ) -> tuple[ParsedProvision, ...]:
        return tuple(
            item for item in ancestors if item.provision_type in STRUCTURAL_TYPES
        )

    @staticmethod
    def _article_ancestor(
        ancestors: tuple[ParsedProvision, ...],
    ) -> ParsedProvision | None:
        return next(
            (
                item
                for item in reversed(ancestors)
                if item.provision_type is ProvisionType.ARTICLE
            ),
            None,
        )

    def _context_path(
        self, ancestors: tuple[ParsedProvision, ...]
    ) -> tuple[ParsedProvision, ...]:
        path: list[ParsedProvision] = []
        for ancestor in ancestors:
            if ancestor.provision_type is ProvisionType.ARTICLE:
                path.append(ancestor)
                caput = next(
                    (
                        child
                        for child in ancestor.children
                        if child.provision_type is ProvisionType.CAPUT
                    ),
                    None,
                )
                if caput is not None:
                    path.append(caput)
            elif ancestor.provision_type in CONTEXTUAL_TYPES:
                path.append(ancestor)
        return tuple(path)

    @staticmethod
    def _metadata_search_text(act: ParsedAct, kind: str, citation_text: str) -> str:
        label = METADATA_RETRIEVAL_LABELS.get(kind)
        parts = (act.code, act.title, label, citation_text)
        return "\n".join(part for part in parts if part)

    def _walk(
        self,
        provisions: tuple[ParsedProvision, ...],
        ancestors: tuple[ParsedProvision, ...] = (),
    ):
        for provision in sorted(provisions, key=lambda item: item.document_order):
            yield _LocatedProvision(provision, ancestors)
            yield from self._walk(provision.children, (*ancestors, provision))


def _unique_provisions(
    provisions: tuple[ParsedProvision, ...],
) -> tuple[ParsedProvision, ...]:
    seen: set[str] = set()
    result: list[ParsedProvision] = []
    for provision in provisions:
        if provision.stable_key not in seen:
            seen.add(provision.stable_key)
            result.append(provision)
    return tuple(result)


def _metadata_reference(act_code: str, kind: str) -> str:
    stable_kind = "PROMULGATION_DATE" if kind == "PROMULGATION" else kind
    return f"{act_code}/METADATA:{stable_kind}"


def _stable_reference(act_code: str, stable_key: str) -> str:
    parts = stable_key.split("/")
    article_index = next(
        (index for index, part in enumerate(parts) if part.startswith("ARTICLE:")),
        None,
    )
    if article_index is None:
        return stable_key
    normative = parts[article_index:]
    if len(normative) > 2 and normative[1] == "CAPUT:@caput":
        normative.pop(1)
    return "/".join((act_code, *normative))
