"""Base class every source fetcher implements.

Adding a new source (a company career page, an aggregator API like Adzuna
or JSearch) later means writing one new class here that yields Job objects
— nothing else in the pipeline changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator

from src.schema import Job


class BaseFetcher(ABC):
    source_name: str = "base"

    @abstractmethod
    def search(self, term: str, max_pages: int = 3) -> Iterator[Job]:
        """Yield Job objects matching the search term."""
        raise NotImplementedError
