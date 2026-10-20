"""Integration extension ports. Implementations are intentionally deferred."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from .models import Evidence, ResearchReport, ResearchRequest


class OnlineResearchPort(Protocol):
    def search(self, query: str, *, as_of: datetime | None = None) -> list[Evidence]:
        """Return traced source records; no unsupported synthesis."""


class FundamentalDataPort(Protocol):
    def financials(self, instrument_id: str, *, as_of: datetime | None = None) -> dict[str, Any]:
        """Official / licensed normalized financial statement data."""


class TechnicalDataPort(Protocol):
    def indicators(
        self,
        instrument_id: str,
        timeframe: str,
        *,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        """Read-only data from local files, SysTrd adapter, or another app."""


class ResearchStorePort(Protocol):
    def save(self, report: ResearchReport) -> str:
        """Persist a report and return its durable run identifier."""

    def get(self, run_id: str) -> ResearchReport | None:
        """Retrieve report by identifier."""


class ResearchServicePort(Protocol):
    def analyze(self, request: ResearchRequest) -> ResearchReport:
        """Stable interface consumable by future FA UI, SysTrd or external apps."""
