"""Confidence Scoring Engine (Phase 6 placeholder).

Will use scikit-learn / XGBoost to score extraction confidence
based on token features and historical corrections.
"""

from __future__ import annotations

from app.core.types import RawTransaction, FieldConfidence


class ConfidenceScorer:
    """ML-based confidence scorer — placeholder for Phase 6."""

    def __init__(self, model_path: str | None = None):
        self.model = None
        self.model_path = model_path

    def score(self, transaction: RawTransaction) -> FieldConfidence:
        """Score a transaction. Currently returns the validator-based scores."""
        return transaction.confidence

    def load_model(self) -> bool:
        """Load trained model from disk."""
        # Phase 6: implement model loading
        return False

    @property
    def is_loaded(self) -> bool:
        return self.model is not None
