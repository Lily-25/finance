from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from asset_report.application.app import FinancialAnalysisApp
from asset_report.business.analysis import (
    AssetAnalysisService,
    MetricsCalculator,
    TimeFrameAnalysisResult,
)
from asset_report.data_access.json_repository import (
    DataValidationError,
    JSONFinancialStatementRepository,
)
from asset_report.domain.models import (
    AssetItem,
    AssetReportData,
    AssetStatement,
    Company,
    FinancialTimeSeriesData,
    LiabilityItem,
    LiabilityStatement,
    Money,
    ReportingPeriod,
)
from asset_report.output.charts import AssetCharts
from asset_report.output.reporting import NarrativeGenerator, ReportBuilder, ReportFileExporter
from asset_report.presentation.cli import main


def valid_payload() -> dict[str, object]:
    return {
        "company": "Example & Sons",
        "reporting_period": "31 December 2025",
        "currency": "usd",
        "assets": {
            "current": [
                {"name": "Cash", "amount": "100.25"},
                {"name": "Inventory", "amount": 199.75},
            ],
            "non_current": [
                {"name": "Equipment", "amount": 700},
            ],
        },
        "liabilities": {
            "current": [
                {"name": "Accounts payable", "amount": 200},
            ],
            "non_current": [
                {"name": "Long-term debt", "amount": 300},
            ],
        },
    }


class TemporaryJSONMixin:
    def write_json(self, payload: object) -> Path:
        self.temp_dir = tempfile.TemporaryDirectory()
        path = Path(self.temp_dir.name) / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.addCleanup(self.temp_dir.cleanup)
        return path


class MoneyTests(unittest.TestCase):
    def test_accepts_decimal_compatible_values(self) -> None:
        self.assertEqual(Money.from_value("10.25").amount, Decimal("10.25"))

    def test_rejects_negative_amount(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            Money.from_value(-1)

    def test_rejects_boolean_amount(self) -> None:
        with self.assertRaisesRegex(ValueError, "Boolean"):
            Money.from_value(True)

    def test_rejects_non_finite_amount(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            Money.from_value("NaN")

    def test_money_can_be_summed(self) -> None:
        self.assertEqual(sum([Money.from_value(2), Money.from_value(3)], Money.zero()).amount, 5)


class ExpandedDomainTests(unittest.TestCase):
    def test_company_normalizes_optional_ticker_and_currency(self) -> None:
        company = Company(
            name="  Example Holdings  ",
            ticker=" exm ",
            currency=" usd ",
            reporting_period=ReportingPeriod("  FY 2025  "),
        )
        self.assertEqual(company.name, "Example Holdings")
        self.assertEqual(company.ticker, "EXM")
        self.assertEqual(company.currency, "USD")
        self.assertEqual(company.reporting_period.label, "FY 2025")

    def test_asset_line_items_default_to_zero(self) -> None:
        statement = AssetStatement()
        for field_name in AssetStatement.CURRENT_FIELDS + AssetStatement.NON_CURRENT_FIELDS:
            self.assertEqual(getattr(statement, field_name), Money.zero())
            self.assertEqual(statement.component_percentages[field_name], Decimal("0"))
        self.assertEqual(statement.total_assets, Money.zero())

    def test_asset_totals_and_component_percentages(self) -> None:
        statement = AssetStatement(
            cash_and_cash_equivalents=100,
            inventory=300,
            fixed_assets=600,
        )
        self.assertEqual(statement.total_current_assets.amount, Decimal("400"))
        self.assertEqual(statement.total_non_current_assets.amount, Decimal("600"))
        self.assertEqual(statement.total_assets.amount, Decimal("1000"))
        self.assertEqual(statement.percentage_of_total("cash_and_cash_equivalents"), Decimal("10.0"))
        self.assertEqual(statement.percentage_of_total("Inventory"), Decimal("30.0"))
        self.assertEqual(statement.percentage_of_total("Fixed assets"), Decimal("60.0"))

    def test_asset_factory_maps_aliases_and_preserves_custom_lines(self) -> None:
        statement = AssetStatement.create(
            [
                AssetItem("Cash", Money.from_value(25)),
                AssetItem("Prepaid expenses", Money.from_value(15)),
                AssetItem("Digital assets", Money.from_value(10)),
            ],
            [AssetItem("Property, plant and equipment", Money.from_value(50))],
        )
        self.assertEqual(statement.cash_and_cash_equivalents.amount, Decimal("25"))
        self.assertEqual(statement.prepayments.amount, Decimal("15"))
        self.assertEqual(statement.fixed_assets.amount, Decimal("50"))
        self.assertEqual(statement.additional_current_assets[0].name, "Digital assets")
        self.assertEqual(statement.percentage_of_total("Digital assets"), Decimal("10.0"))

    def test_liability_line_items_default_to_zero(self) -> None:
        statement = LiabilityStatement()
        for field_name in LiabilityStatement.CURRENT_FIELDS + LiabilityStatement.NON_CURRENT_FIELDS:
            self.assertEqual(getattr(statement, field_name), Money.zero())
            self.assertEqual(statement.component_percentages[field_name], Decimal("0"))
        self.assertEqual(statement.total_liabilities, Money.zero())

    def test_liability_totals_and_component_percentages(self) -> None:
        statement = LiabilityStatement(
            accounts_payable=100,
            short_term_debt=200,
            long_term_debt=700,
        )
        self.assertEqual(statement.total_current_liabilities.amount, Decimal("300"))
        self.assertEqual(statement.total_non_current_liabilities.amount, Decimal("700"))
        self.assertEqual(statement.total_liabilities.amount, Decimal("1000"))
        self.assertEqual(statement.percentage_of_total("Accounts payable"), Decimal("10.0"))
        self.assertEqual(statement.percentage_of_total("short_term_debt"), Decimal("20.0"))
        self.assertEqual(statement.percentage_of_total("Long-term debt"), Decimal("70.0"))

    def test_liability_factory_preserves_additional_lines(self) -> None:
        statement = LiabilityStatement.create(
            [LiabilityItem("Accounts payable", Money.from_value(60))],
            [LiabilityItem("Environmental obligation", Money.from_value(40))],
        )
        self.assertEqual(statement.accounts_payable.amount, Decimal("60"))
        self.assertEqual(
            statement.additional_non_current_liabilities[0].name,
            "Environmental obligation",
        )
        self.assertEqual(
            statement.percentage_of_total("Environmental obligation"), Decimal("40.0")
        )


class RepositoryTests(TemporaryJSONMixin, unittest.TestCase):
    def test_loads_and_standardizes_valid_json(self) -> None:
        payload = valid_payload()
        payload["company"] = "  Example & Sons  "
        data = JSONFinancialStatementRepository(self.write_json(payload)).load()
        self.assertEqual(data.company.name, "Example & Sons")
        self.assertIsNone(data.company.ticker)
        self.assertEqual(data.currency, "USD")
        self.assertEqual(len(data.statement.current_assets), 2)
        self.assertEqual(data.liabilities.total_liabilities.amount, Decimal("500"))

    def test_asset_only_input_remains_backward_compatible(self) -> None:
        payload = valid_payload()
        del payload["liabilities"]
        data = JSONFinancialStatementRepository(self.write_json(payload)).load()
        self.assertEqual(data.liabilities.total_liabilities, Money.zero())

    def test_liability_sections_are_validated_with_precise_locations(self) -> None:
        payload = valid_payload()
        payload["liabilities"]["current"][0]["amount"] = "abc"  # type: ignore[index]
        with self.assertRaisesRegex(
            DataValidationError, r"liabilities\.current\[0\]\.amount"
        ):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_missing_root_field_is_rejected(self) -> None:
        payload = valid_payload()
        del payload["currency"]
        with self.assertRaisesRegex(DataValidationError, "currency"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_optional_ticker_is_mapped_and_validated(self) -> None:
        payload = valid_payload()
        payload["ticker"] = " exm "
        data = JSONFinancialStatementRepository(self.write_json(payload)).load()
        self.assertEqual(data.company.ticker, "EXM")

        payload["ticker"] = 123
        with self.assertRaisesRegex(DataValidationError, "ticker"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_missing_asset_section_is_rejected(self) -> None:
        payload = valid_payload()
        del payload["assets"]["non_current"]  # type: ignore[index]
        with self.assertRaisesRegex(DataValidationError, "non_current"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_duplicate_names_with_different_case_are_rejected(self) -> None:
        payload = valid_payload()
        payload["assets"]["current"].append({"name": "cash", "amount": 2})  # type: ignore[index]
        with self.assertRaisesRegex(DataValidationError, "Duplicate"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_invalid_amount_has_field_location(self) -> None:
        payload = valid_payload()
        payload["assets"]["current"][0]["amount"] = "abc"  # type: ignore[index]
        with self.assertRaisesRegex(DataValidationError, r"assets\.current\[0\]\.amount"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_empty_asset_lists_are_rejected(self) -> None:
        payload = valid_payload()
        payload["assets"] = {"current": [], "non_current": []}
        with self.assertRaisesRegex(DataValidationError, "At least one"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_invalid_json_reports_line_and_column(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "bad.json"
        path.write_text('{"company":', encoding="utf-8")
        with self.assertRaisesRegex(DataValidationError, "line 1, column"):
            JSONFinancialStatementRepository(path).load()

    def test_missing_file_has_clear_error(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "not found"):
            JSONFinancialStatementRepository("definitely-missing.json").load()


class AnalysisTests(TemporaryJSONMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.data = JSONFinancialStatementRepository(self.write_json(valid_payload())).load()
        self.result = AssetAnalysisService().analyze(self.data)

    def test_calculates_totals_exactly(self) -> None:
        self.assertEqual(self.result.current_total.amount, Decimal("300.00"))
        self.assertEqual(self.result.non_current_total.amount, Decimal("700"))
        self.assertEqual(self.result.total_assets.amount, Decimal("1000.00"))

    def test_calculates_class_percentages(self) -> None:
        self.assertEqual(self.result.current_percentage, Decimal("30.0"))
        self.assertEqual(self.result.non_current_percentage, Decimal("70.0"))

    def test_ranks_categories_by_amount(self) -> None:
        self.assertEqual(
            [item.name for item in self.result.all_metrics],
            ["Equipment", "Inventory", "Cash and cash equivalents"],
        )

    def test_calculates_item_share_of_total(self) -> None:
        self.assertEqual(self.result.all_metrics[0].percentage_of_total, Decimal("70.0"))

    def test_calculates_liability_totals_and_position_ratios(self) -> None:
        self.assertEqual(self.result.current_liabilities_total.amount, Decimal("200"))
        self.assertEqual(self.result.non_current_liabilities_total.amount, Decimal("300"))
        self.assertEqual(self.result.total_liabilities.amount, Decimal("500"))
        self.assertEqual(self.result.liability_to_assets_percentage, Decimal("50.0"))
        self.assertEqual(self.result.net_assets, Decimal("500.00"))
        self.assertEqual(self.result.current_ratio, Decimal("1.5000"))

    def test_ranks_liability_categories(self) -> None:
        self.assertEqual(
            [item.name for item in self.result.all_liability_metrics],
            ["Long-term debt", "Accounts payable"],
        )

    def test_zero_denominator_percentage_is_zero(self) -> None:
        self.assertEqual(MetricsCalculator.percentage(Money.zero(), Money.zero()), Decimal("0"))

    def test_all_zero_assets_are_rejected_by_analysis(self) -> None:
        data = AssetReportData(
            company=Company("Example", "USD", ReportingPeriod("2025")),
            statement=AssetStatement.create([AssetItem("Cash", Money.zero())], []),
        )
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            AssetAnalysisService().analyze(data)


class OutputTests(TemporaryJSONMixin, unittest.TestCase):
    def setUp(self) -> None:
        data = JSONFinancialStatementRepository(self.write_json(valid_payload())).load()
        self.result = AssetAnalysisService().analyze(data)
        self.charts = AssetCharts().generate(self.result)

    def test_generates_exactly_four_charts(self) -> None:
        self.assertEqual(len(self.charts), 4)
        self.assertEqual(
            [chart.title for chart in self.charts],
            [
                "Asset structure",
                "Liability structure",
                "Largest asset categories",
                "Largest liability categories",
            ],
        )

    def test_charts_are_inline_accessible_svg(self) -> None:
        for chart in self.charts:
            self.assertIn("<svg", chart.svg)
            self.assertIn('role="img"', chart.svg)
            self.assertIn("<title>", chart.svg)

    def test_narrative_uses_calculated_values(self) -> None:
        narrative = " ".join(NarrativeGenerator().generate(self.result))
        self.assertIn("70.0%", narrative)
        self.assertIn("Equipment", narrative)
        self.assertIn("USD 700.00", narrative)

    def test_report_is_standalone_and_contains_four_svgs(self) -> None:
        html = ReportBuilder().build(self.result, self.charts)
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertEqual(html.count('<svg class="chart-svg"'), 4)
        self.assertNotIn("<script", html)
        self.assertNotIn("https://", html)
        self.assertIn("Liability detail", html)
        self.assertIn("Total liabilities", html)

    def test_report_escapes_data(self) -> None:
        html = ReportBuilder().build(self.result, self.charts)
        self.assertIn("Example &amp; Sons", html)
        self.assertNotIn("Example & Sons</h1>", html)

    def test_exporter_creates_parent_directories(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        destination = Path(temp_dir.name) / "nested" / "report.html"
        result = ReportFileExporter().export("<html></html>", destination)
        self.assertEqual(result, destination.resolve())
        self.assertEqual(destination.read_text(encoding="utf-8"), "<html></html>")


class TimeFrameTests(TemporaryJSONMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.input_path = self.project_root / "sample_data" / "time_frame_input.json"
        self.data = JSONFinancialStatementRepository(self.input_path).load()
        self.assertIsInstance(self.data, FinancialTimeSeriesData)
        self.result = AssetAnalysisService().analyze(self.data)
        self.assertIsInstance(self.result, TimeFrameAnalysisResult)

    def test_maps_ordered_financial_periods(self) -> None:
        self.assertEqual(
            [statement.reporting_period.label for statement in self.data.statements],
            ["2023", "2024", "2025", "2026Q3"],
        )
        self.assertEqual(self.data.time_frame, "2023 to 2026Q3")

    def test_calculates_time_frame_changes(self) -> None:
        self.assertEqual(self.result.first.total_assets.amount, Decimal("12000000"))
        self.assertEqual(self.result.latest.total_assets.amount, Decimal("22000000"))
        self.assertEqual(
            self.result.asset_change_percentage.quantize(Decimal("0.1")),
            Decimal("83.3"),
        )
        self.assertEqual(self.result.first.total_liabilities.amount, Decimal("7000000"))
        self.assertEqual(self.result.latest.total_liabilities.amount, Decimal("9900000"))
        self.assertEqual(self.result.latest.net_assets, Decimal("12100000"))

    def test_generates_four_time_series_charts(self) -> None:
        charts = AssetCharts().generate(self.result)
        self.assertEqual(
            [chart.title for chart in charts],
            [
                "Assets and liabilities over time",
                "Net assets trend",
                "Current ratio trend",
                "Liabilities to assets",
            ],
        )
        for chart in charts:
            self.assertIn('<svg class="chart-svg"', chart.svg)
            self.assertIn('role="img"', chart.svg)

    def test_builds_time_frame_report_and_narrative(self) -> None:
        charts = AssetCharts().generate(self.result)
        html = ReportBuilder().build(self.result, charts)
        narrative = " ".join(NarrativeGenerator().generate(self.result))
        self.assertEqual(html.count('<svg class="chart-svg"'), 4)
        self.assertIn("Period comparison", html)
        self.assertIn("2026Q3", html)
        self.assertIn("83.3%", narrative)
        self.assertIn("USD 22,000,000.00", narrative)

    def test_rejects_duplicate_period_labels(self) -> None:
        payload = json.loads(self.input_path.read_text(encoding="utf-8"))
        payload["periods"][1]["reporting_period"] = "2023"
        with self.assertRaisesRegex(DataValidationError, "unique"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_rejects_time_frame_boundary_mismatch(self) -> None:
        payload = json.loads(self.input_path.read_text(encoding="utf-8"))
        payload["time_frame"]["end"] = "2026"
        with self.assertRaisesRegex(DataValidationError, "must match"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_rejects_periods_out_of_order(self) -> None:
        payload = json.loads(self.input_path.read_text(encoding="utf-8"))
        payload.pop("time_frame")
        payload["periods"][0], payload["periods"][1] = (
            payload["periods"][1],
            payload["periods"][0],
        )
        with self.assertRaisesRegex(DataValidationError, "chronological"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_application_generates_time_frame_report(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        output_path = Path(temp_dir.name) / "time-frame-report.html"
        generated = FinancialAnalysisApp().generate_financial_report(
            self.input_path, output_path
        )
        self.assertEqual(generated, output_path.resolve())
        self.assertIn("Time-series analysis", output_path.read_text(encoding="utf-8"))


class IntegrationTests(TemporaryJSONMixin, unittest.TestCase):
    def test_comprehensive_main_input_covers_every_standard_field(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        data = JSONFinancialStatementRepository(
            project_root / "sample_data" / "main_input.json"
        ).load()
        for field_name in AssetStatement.CURRENT_FIELDS + AssetStatement.NON_CURRENT_FIELDS:
            self.assertGreater(getattr(data.statement, field_name).amount, 0)
        self.assertEqual(data.statement.total_current_assets.amount, Decimal("6500000"))
        self.assertEqual(data.statement.total_non_current_assets.amount, Decimal("13500000"))
        self.assertEqual(data.statement.total_assets.amount, Decimal("20000000"))
        for field_name in LiabilityStatement.CURRENT_FIELDS + LiabilityStatement.NON_CURRENT_FIELDS:
            self.assertGreater(getattr(data.liabilities, field_name).amount, 0)
        self.assertEqual(data.liabilities.total_current_liabilities.amount, Decimal("3500000"))
        self.assertEqual(
            data.liabilities.total_non_current_liabilities.amount, Decimal("6000000")
        )
        self.assertEqual(data.liabilities.total_liabilities.amount, Decimal("9500000"))
        self.assertEqual(data.company.ticker, "OIG")

    def test_application_generates_complete_report(self) -> None:
        input_path = self.write_json(valid_payload())
        output_path = Path(self.temp_dir.name) / "report.html"
        generated = FinancialAnalysisApp().generate_asset_report(input_path, output_path)
        self.assertEqual(generated, output_path.resolve())
        html = output_path.read_text(encoding="utf-8")
        self.assertIn("Asset detail", html)
        self.assertIn("Liability detail", html)

    def test_cli_returns_success_and_prints_destination(self) -> None:
        input_path = self.write_json(valid_payload())
        output_path = Path(self.temp_dir.name) / "report.html"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main([str(input_path), "--output", str(output_path)])
        self.assertEqual(exit_code, 0)
        self.assertIn(str(output_path.resolve()), stdout.getvalue())

    def test_cli_returns_error_for_bad_input(self) -> None:
        input_path = self.write_json({})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main([str(input_path)])
        self.assertEqual(exit_code, 1)
        self.assertIn("Missing required field", stderr.getvalue())

    def test_package_main_supports_direct_file_execution(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [sys.executable, str(project_root / "asset_report" / "__main__.py"), "--help"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Generate a polished", completed.stdout)


if __name__ == "__main__":
    unittest.main()
