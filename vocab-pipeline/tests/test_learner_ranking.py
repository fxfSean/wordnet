import pytest

from vocab_pipeline.learner_ranking import validate_ranking
from vocab_pipeline.learner_view import learner_entry


@pytest.mark.parametrize(
    "value",
    [
        '{"primary": [], "more": ["a"]}',
        '{"primary": ["a"], "more": ["a"]}',
        '{"primary": ["unknown"], "more": []}',
        '{"primary": ["a"], "more": [], "definition": "rewritten"}',
    ],
)
def test_invalid_ai_ranking_is_rejected(value):
    with pytest.raises(ValueError):
        validate_ranking(value, {"a", "b"})


def test_ai_order_preserves_original_definitions():
    word = {
        "lemma": "bank",
        "candidates": [
            {
                "sense_id": identifier,
                "selection_status": "candidate",
                "pos": "noun",
                "source_definition": definition,
                "source_examples": [],
            }
            for identifier, definition in (("a", "Original first"), ("b", "Original second"))
        ],
    }
    result = learner_entry(word, {"primary": ["b"], "more": ["a"]})
    assert result["ranking_source"] == "ai_selection"
    assert [
        (sense["sense_id"], sense["is_primary"], sense["definition_en"])
        for sense in result["senses"]
    ] == [("b", True, "Original second"), ("a", False, "Original first")]
