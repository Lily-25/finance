"""Ports implemented by the data-access layer."""

from __future__ import annotations

from typing import Protocol

from .models import AssetReportData


class FinancialStatementRepository(Protocol):
    def load(self) -> AssetReportData:
        """Load one structured financial statement."""

