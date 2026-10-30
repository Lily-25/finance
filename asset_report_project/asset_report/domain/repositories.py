"""Ports implemented by the data-access layer."""

from __future__ import annotations

from typing import Protocol

from .models import FinancialStatementData, FinancialTimeSeriesData


class FinancialStatementRepository(Protocol):
    def load(self) -> FinancialStatementData | FinancialTimeSeriesData:
        """Load one structured financial statement."""
