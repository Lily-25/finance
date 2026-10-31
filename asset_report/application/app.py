"""Public application facade and dependency configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..business.analysis import FinancialAnalysisService, TimeFrameAnalysisResult
from ..data_access.json_repository import JSONFinancialStatementRepository
from ..output.charts import FinancialCharts
from ..output.reporting import ReportBuilder, ReportFileExporter
from ..domain.statement_bundle import StatementQuery
from .statement_tasks import RetrieveAndNormalizeThreeStatements, StatementExportResult
from .use_cases import GenerateTimeFrameReport, as_time_frame_data


@dataclass(frozen=True)
class ApplicationConfig:
    default_output: Path = Path("build/time-frame-report.html")


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
