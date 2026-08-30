from evaluation.forensics_91_2 import locator_mismatch


def test_locator_mismatch_detects_wrong_inciso() -> None:
    assert locator_mismatch(
        [{"text": "art. 5º, inciso XLVIII, alínea a"}],
        [{"label": "CF/88, ALINEA a (identidade: ARTICLE:5/INCISO:XLVII/ALINEA:A)"}],
    )


def test_locator_without_explicit_reference_does_not_fail() -> None:
    assert not locator_mismatch(
        [{"text": "A liberdade é protegida."}],
        [{"label": "CF/88, INCISO VI (identidade: ARTICLE:5/INCISO:VI)"}],
    )
