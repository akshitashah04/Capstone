"""Pinned inputs and versioned output location for a reproducible search index."""

SOURCE_DATASET_REPO = "Tox1/LibrariesBookData"
SOURCE_REVISION = "daba70f6e6de9f7a5c9a1f830fd255415c6d6bb7"
MODEL_REPO = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
RERANKER_REPO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
RERANKER_REVISION = "1427fd652930e4ba29e8149678df786c240d8825"
EMBEDDING_DIMENSIONS = 384
INDEX_VERSION = 2
INDEX_PREFIX = f"search/v{INDEX_VERSION}"
