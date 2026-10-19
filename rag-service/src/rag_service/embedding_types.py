"""Shared embedding records used by providers and the repository."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingSpace:
    provider: str
    model: str
    revision: str
    dimensions: int


@dataclass
class EmbeddingBatch:
    space: EmbeddingSpace
    vectors: list[list[float]]
