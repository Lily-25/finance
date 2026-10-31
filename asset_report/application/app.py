"""Public application facade and dependency configuration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

from ..business.analysis import FinancialAnalysisService, TimeFrameAnalysisResult
from ..business.ratios import (
    FinancialRatioAnalysisResult,
    FinancialRatioAnalysisService,
)
from ..data_access.json_repository import JSONFinancialStatementRepository
from ..data_access.statement_repository import JSONStatementDirectoryRepository
from ..output.charts import FinancialCharts
from ..output.ratio_reporting import FinancialRatioReportBuilder
from ..output.reporting import ReportBuilder, ReportFileExporter
from ..domain.statement_bundle import StatementQuery
from .statement_tasks import RetrieveAndNormalizeThreeStatements, StatementExportResult
from .use_cases import GenerateTimeFrameReport, as_time_frame_data


@dataclass(frozen=True)
class ApplicationConfig:
    default_output: Path = Path("build/time-frame-report.html")
    default_ratio_output: Path = Path("build/financial-ratio-report.html")


class DependencyContainer:
    def financial_analysis_service(self) -> FinancialAnalysisService:
        return FinancialAnalysisService()

    def generate_time_frame_report(self) -> GenerateTimeFrameReport:
        return GenerateTimeFrameReport(
            analysis_service=self.financial_analysis_service(),
            chart_generator=FinancialCharts(),
            report_builder=ReportBuilder(),
            exporter=ReportFileExporter(),
        )

    def financial_ratio_analysis_service(self) -> FinancialRatioAnalysisService:
        return FinancialRatioAnalysisService()

    def financial_ratio_report_builder(self) -> FinancialRatioReportBuilder:
        return FinancialRatioReportBuilder()

    def report_exporter(self) -> ReportFileExporter:
        return ReportFileExporter()


class FinancialAnalysisApp:
    def __init__(
        self,
        config: ApplicationConfig | None = None,
        container: DependencyContainer | None = None,
    ) -> None:
        self.config = config or ApplicationConfig()
        self.container = container or DependencyContainer()

    def analyze_time_frame(
        self, input_paths: str | Path | Sequence[str | Path]
    ) -> TimeFrameAnalysisResult:
        """Analyze one or more financial-period files through one interface."""

        period_paths = self._normalize_period_paths(input_paths)
        data = as_time_frame_data(JSONFinancialStatementRepository(period_paths).load())
        result = self.container.financial_analysis_service().analyze(data)
        if not isinstance(result, TimeFrameAnalysisResult):
            raise RuntimeError("Expected a time-frame analysis result")
        return result

    def generate_time_frame_report(
        self,
        input_paths: str | Path | Sequence[str | Path],
        output_path: str | Path | None = None,
        title: str | None = None,
    ) -> Path:
        """Generate a time-frame report from one or more period files."""

        period_paths = self._normalize_period_paths(input_paths)
        destination = output_path or self.config.default_output
        repository = JSONFinancialStatementRepository(period_paths)
        return self.container.generate_time_frame_report().execute(
            repository, destination, report_title=title
        )

    def retrieve_three_statements(
        self,
        source_directory: str | Path,
        output_directory: str | Path,
        *,
        company: str,
        start_period: str,
        end_period: str,
        schema_profile: str,
    ) -> StatementExportResult:
        """Retrieve and normalize a complete three-statement time frame."""

        query = StatementQuery(
            company=company,
            start_period=start_period,
            end_period=end_period,
            schema_profile=schema_profile,
        )
        return RetrieveAndNormalizeThreeStatements().execute(
            source_directory, output_directory, query
        )

    def analyze_financial_ratios(
        self,
        source_directory: str | Path,
        *,
        company: str,
        start_period: str,
        end_period: str,
        schema_profile: str,
        market_prices: Mapping[str, Decimal | int | float | str] | None = None,
    ) -> FinancialRatioAnalysisResult:
        """Calculate cross-statement financial ratios for an inclusive time frame."""

        query = StatementQuery(
            company=company,
            start_period=start_period,
            end_period=end_period,
            schema_profile=schema_profile,
        )
        bundle = JSONStatementDirectoryRepository(source_directory).retrieve(query)
        return self.container.financial_ratio_analysis_service().analyze(
            bundle, market_prices=market_prices
        )

    def generate_financial_ratio_report(
        self,
        source_directory: str | Path,
        output_path: str | Path | None = None,
        *,
        company: str,
        start_period: str,
        end_period: str,
        schema_profile: str,
        title: str | None = None,
        market_prices: Mapping[str, Decimal | int | float | str] | None = None,
    ) -> Path:
        """Generate a stand-alone financial-ratio trend report."""

        result = self.analyze_financial_ratios(
            source_directory,
            company=company,
            start_period=start_period,
            end_period=end_period,
            schema_profile=schema_profile,
            market_prices=market_prices,
        )
        html = self.container.financial_ratio_report_builder().build(result, title)
        destination = output_path or self.config.default_ratio_output
        return self.container.report_exporter().export(html, destination)

    @staticmethod
    def _normalize_period_paths(
        input_paths: str | Path | Sequence[str | Path],
    ) -> tuple[str | Path, ...]:
        if isinstance(input_paths, (str, Path)):
            period_paths = (input_paths,)
        else:
            period_paths = tuple(input_paths)
        if not period_paths:
            raise ValueError("Time-frame analysis requires at least one period file")
        return period_paths
