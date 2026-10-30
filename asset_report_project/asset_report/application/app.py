"""Public application facade and dependency configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..business.analysis import (
    FinancialAnalysisResult,
    FinancialAnalysisService,
    TimeFrameAnalysisResult,
)
from ..data_access.json_repository import JSONFinancialStatementRepository
from ..domain.models import FinancialTimeSeriesData
from ..output.charts import FinancialCharts
from ..output.reporting import ReportBuilder, ReportFileExporter
from .use_cases import GenerateFinancialReport


@dataclass(frozen=True)
class ApplicationConfig:
    default_output: Path = Path("build/financial-report.html")
    default_time_frame_output: Path = Path("build/time-frame-report.html")


class DependencyContainer:
    def financial_analysis_service(self) -> FinancialAnalysisService:
        return FinancialAnalysisService()

    def generate_financial_report(self) -> GenerateFinancialReport:
        return GenerateFinancialReport(
            analysis_service=self.financial_analysis_service(),
            chart_generator=FinancialCharts(),
            report_builder=ReportBuilder(),
            exporter=ReportFileExporter(),
        )

    def generate_asset_report(self) -> GenerateFinancialReport:
        """Backward-compatible dependency factory."""

        return self.generate_financial_report()


class FinancialAnalysisApp:
    def __init__(
        self,
        config: ApplicationConfig | None = None,
        container: DependencyContainer | None = None,
    ) -> None:
        self.config = config or ApplicationConfig()
        self.container = container or DependencyContainer()

    def generate_financial_report(
        self,
        input_path: str | Path | Sequence[str | Path],
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        repository = JSONFinancialStatementRepository(input_path)
        destination = output_path or self.config.default_output
        return self.container.generate_financial_report().execute(
            repository, destination, report_title=title
        )

    def analyze_financial_data(
        self, input_path: str | Path | Sequence[str | Path]
    ) -> FinancialAnalysisResult | TimeFrameAnalysisResult:
        """Load and analyze one statement or a sequence of period statements."""

        data = JSONFinancialStatementRepository(input_path).load()
        return self.container.financial_analysis_service().analyze(data)

    def analyze_time_frame(
        self, input_paths: Sequence[str | Path]
    ) -> TimeFrameAnalysisResult:
        """Analyze two or more separate financial-period files."""

        period_paths = self._require_period_paths(input_paths)
        data = JSONFinancialStatementRepository(period_paths).load()
        if not isinstance(data, FinancialTimeSeriesData):
            raise ValueError("Time-frame analysis requires separate period files")
        result = self.container.financial_analysis_service().analyze(data)
        if not isinstance(result, TimeFrameAnalysisResult):
            raise RuntimeError("Expected a time-frame analysis result")
        return result

    def generate_time_frame_report(
        self,
        input_paths: Sequence[str | Path],
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        """Generate a trend report from two or more separate period files."""

        period_paths = self._require_period_paths(input_paths)
        destination = output_path or self.config.default_time_frame_output
        return self.generate_financial_report(period_paths, destination, title)

    def generate_asset_report(
        self,
        input_path: str | Path | Sequence[str | Path],
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        """Backward-compatible facade method."""

        return self.generate_financial_report(input_path, output_path, title)

    @staticmethod
    def _require_period_paths(
        input_paths: Sequence[str | Path],
    ) -> tuple[str | Path, ...]:
        if isinstance(input_paths, (str, Path)):
            raise ValueError("Time-frame analysis requires at least two period files")
        period_paths = tuple(input_paths)
        if len(period_paths) < 2:
            raise ValueError("Time-frame analysis requires at least two period files")
        return period_paths
