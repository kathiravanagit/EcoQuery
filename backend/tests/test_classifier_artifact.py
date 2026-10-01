"""Guards for the trained artifact in models/pipeline.pkl.

Every other test in test_classifier.py runs with ECO_QUERY_TESTING=1, which
bypasses the model entirely. That is why a bad artifact shipped unnoticed: a
script refit the pipeline on 10 mock queries (85-term vocabulary) and cut
classifier accuracy from 86.7% to 56.7% with no failing test. These checks
pin the artifact's identity so that cannot happen again.
"""

import os
import sys

import joblib
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "pipeline.pkl"
)


@pytest.fixture(scope="module")
def pipeline():
    if not os.path.exists(MODEL_PATH):
        pytest.skip("pipeline.pkl not built; run backend/train_classifier.py")
    return joblib.load(MODEL_PATH)


def test_artifact_has_a_real_vocabulary(pipeline):
    """The clobbered artifact had 85 terms; the trainer's has ~1,500."""
    vocab = pipeline.named_steps["tfidf"].vocabulary_
    assert len(vocab) > 500, (
        "pipeline.pkl looks like the 10-mock-query artifact "
        f"({len(vocab)} terms). Re-run backend/train_classifier.py."
    )


def test_artifact_uses_training_hyperparameters(pipeline):
    """These four fingerprints separate the trainer from the eval script."""
    tfidf = pipeline.named_steps["tfidf"]
    assert tfidf.max_features == 10000
    assert tfidf.sublinear_tf is True
    assert list(pipeline.named_steps["clf"].classes_) == [
        "complex", "medium", "simple",
    ]


def test_headline_proof_prompt_is_complex(pipeline):
    """Regression: this prompt was classified `simple` by the bad artifact."""
    prompt = (
        "Analyze the time complexity of quicksort and prove its average case."
    )
    assert pipeline.predict([prompt])[0] == "complex"


def test_trivial_prompt_is_simple(pipeline):
    assert pipeline.predict(["What is the capital of France?"])[0] == "simple"
