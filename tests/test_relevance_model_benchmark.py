from evaluation.relevance_model_benchmark_90 import classify, frozen_pairs


def test_frozen_pairs_include_required_controls_and_targets() -> None:
    names = {item.name for item in frozen_pairs()}
    assert {
        "TRUE_BUT_IRRELEVANT",
        "WRONG_LEGAL_ACTOR",
        "VALID_PARAPHRASE",
        "rw-pena-morte",
        "rw-prisao-perpetua",
    } <= names


def test_score_zone_is_fail_closed() -> None:
    assert classify(0.1, 0.2, 0.8) == "IRRELEVANT"
    assert classify(0.9, 0.2, 0.8) == "RELEVANT"
    assert classify(0.5, 0.2, 0.8) == "UNRESOLVED"
