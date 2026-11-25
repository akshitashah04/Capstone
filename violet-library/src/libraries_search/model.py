"""Load the pinned open-source multilingual text model for our own inference."""

from libraries_search.config import (
    MODEL_REPO,
    MODEL_REVISION,
    RERANKER_REPO,
    RERANKER_REVISION,
)


def load_model(repo: str = MODEL_REPO, revision: str = MODEL_REVISION):
    """Import heavy inference dependencies only in cloud build or demo runs."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(repo, revision=revision, device="cpu", trust_remote_code=False)


def load_reranker(repo: str = RERANKER_REPO, revision: str = RERANKER_REVISION):
    """Load a fixed, multilingual pair scorer for our own candidate reranking."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(repo, revision=revision, device="cpu", trust_remote_code=False)
