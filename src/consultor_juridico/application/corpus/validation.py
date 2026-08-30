"""Invariantes de identidade verificadas antes da persistência do corpus."""

from consultor_juridico.domain import (
    DuplicateProvisionStableKey,
    ParsedCorpus,
    ParsedProvision,
)


def validate_unique_provision_keys(parsed: ParsedCorpus) -> None:
    """Garante unicidade global por ActVersion ainda em memória."""
    for act in parsed.acts:
        seen: dict[str, ParsedProvision] = {}
        for provision in _walk(act.root_provisions):
            previous = seen.setdefault(provision.stable_key, provision)
            if previous is not provision:
                raise DuplicateProvisionStableKey(
                    provision.stable_key,
                    previous.source_locator,
                    provision.source_locator,
                )


def _walk(provisions: tuple[ParsedProvision, ...]):
    for provision in provisions:
        yield provision
        yield from _walk(provision.children)
