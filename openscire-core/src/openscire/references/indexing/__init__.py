from openscire.references.indexing.backends.faiss_backend import FaissBackend
from openscire.references.indexing.backends.local_backend import LocalBackend
from openscire.references.indexing.filters import (
    AndFilter,
    FieldFilter,
    FilterExpression,
    FilterOperator,
    NotFilter,
    OrFilter,
    and_,
    evaluate,
    field,
    not_,
    or_,
)
from openscire.references.indexing.index import EmbeddingIndex
from openscire.references.indexing.models import IndexedDocument, SearchResult
from openscire.references.indexing.reranker import CrossEncoderReranker

__all__ = [
    "EmbeddingIndex",
    "IndexedDocument",
    "SearchResult",
    "FaissBackend",
    "LocalBackend",
    "CrossEncoderReranker",
    "FilterExpression",
    "FilterOperator",
    "FieldFilter",
    "AndFilter",
    "OrFilter",
    "NotFilter",
    "evaluate",
    "field",
    "and_",
    "or_",
    "not_",
]
