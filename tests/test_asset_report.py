from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen
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
from asset_report.data_access.statement_repository import (
    JSONStatementDirectoryRepository,
    SchemaCatalog,
)
from asset_report.domain.models import (
    AssetItem,
    AssetReportData,
    AssetStatement,
    Company,
    EquityItem,
    EquityStatement,
    FinancialTimeSeriesData,
    LiabilityItem,
    LiabilityStatement,
    Money,
    ReportingPeriod,
    SignedMoney,
)
from asset_report.domain.statement_bundle import StatementQuery
from asset_report.output.charts import AssetCharts
from asset_report.output.reporting import NarrativeGenerator, ReportBuilder, ReportFileExporter
from asset_report.presentation.cli import main
from asset_report.presentation.web import AnalysisTaskManager, create_server
from asset_report.runtime import create_run_directory


def line_item(name: str, amount: object, source_field: str | None = None) -> dict[str, object]:
    return {
        "name": name,
        "amount": amount,
        "source_field": source_field or name,
        "description": f"Source balance-sheet line '{source_field or name}'.",
    }


def valid_payload() -> dict[str, object]:
    return {
        "company": "Example & Sons",
        "reporting_period": "31 December 2025",
        "currency": "usd",
        "assets": {
            "current": [
                line_item("Cash", "100.25", "Cash and cash equivalents"),
                line_item("Inventory", 199.75),
            ],
            "non_current": [
                line_item("Equipment", 700, "Property, plant and equipment"),
            ],
        },
        "liabilities": {
            "current": [
                line_item("Accounts payable", 200),
            ],
            "non_current": [
                line_item("Long-term debt", 300),
            ],
        },
        "equity": {
            "items": [line_item("Share capital", 500)],
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

    def test_signed_money_accepts_negative_equity_amount(self) -> None:
        self.assertEqual(SignedMoney.from_value("-10.25").amount, Decimal("-10.25"))


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

    def test_equity_maps_source_labels_and_applies_deductions(self) -> None:
        statement = EquityStatement.create(
            [
                EquityItem(
                    "Company registered capital",
                    SignedMoney.from_value(600),
                    source_field="股本",
                    description="Filed as 股本 in the source statement.",
                ),
                EquityItem(
                    "Repurchased shares",
                    SignedMoney.from_value(100),
                    source_field="减：库存股",
                    description="Filed as a deduction from equity.",
                    is_deduction=True,
                ),
                EquityItem(
                    "Company-specific reserve",
                    SignedMoney.from_value(25),
                    source_field="自定义储备",
                    description="Source line not present in the canonical field list.",
                ),
            ]
        )
        self.assertEqual(statement.share_capital.amount, Decimal("600"))
        self.assertEqual(statement.treasury_shares.amount, Decimal("-100"))
        self.assertEqual(statement.additional_equity[0].name, "Company-specific reserve")
        self.assertEqual(statement.total_equity.amount, Decimal("525"))


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

    def test_complete_financial_position_sections_are_required(self) -> None:
        payload = valid_payload()
        del payload["liabilities"]
        del payload["equity"]
        with self.assertRaisesRegex(DataValidationError, "liabilities, equity"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_source_field_and_description_are_required(self) -> None:
        payload = valid_payload()
        del payload["assets"]["current"][0]["description"]  # type: ignore[index]
        with self.assertRaisesRegex(DataValidationError, r"assets\.current\[0\]\.description"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

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
            ["Fixed assets", "Inventory", "Cash and cash equivalents"],
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

    def test_calculates_equity_and_balances_accounting_equation(self) -> None:
        self.assertEqual(self.result.total_equity.amount, Decimal("500"))
        self.assertEqual(self.result.equity_to_assets_percentage, Decimal("50.0"))
        self.assertEqual(self.result.balance_difference, Decimal("0.00"))
        self.assertTrue(self.result.is_balanced)
        self.assertEqual(self.result.all_equity_metrics[0].source_field, "Share capital")

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
        self.assertIn("Fixed assets", narrative)
        self.assertIn("USD 700.00", narrative)

    def test_report_is_standalone_and_contains_four_svgs(self) -> None:
        html = ReportBuilder().build(self.result, self.charts)
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertEqual(html.count('<svg class="chart-svg"'), 4)
        self.assertNotIn("<script", html)
        self.assertNotIn("https://", html)
        self.assertIn("Liability detail", html)
        self.assertIn("Total liabilities", html)
        self.assertIn("Equity detail", html)
        self.assertIn("Source field", html)
        self.assertIn("Description", html)

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
        self.input_paths = sorted(
            (self.project_root / "sample_data").glob(
                "gotion_high_tech_co_ltd_*.json"
            )
        )
        self.data = JSONFinancialStatementRepository(self.input_paths).load()
        self.assertIsInstance(self.data, FinancialTimeSeriesData)
        self.result = AssetAnalysisService().analyze(self.data)
        self.assertIsInstance(self.result, TimeFrameAnalysisResult)

    def bundled_payload(self) -> dict[str, object]:
        snapshots = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in self.input_paths
        ]
        first = snapshots[0]
        return {
            "company": first["company"],
            "ticker": first["ticker"],
            "currency": first["currency"],
            "time_frame": {"start": "2023", "end": "2026Q3"},
            "periods": [
                {
                    "reporting_period": snapshot["reporting_period"],
                    "assets": snapshot["assets"],
                    "liabilities": snapshot["liabilities"],
                    "equity": snapshot["equity"],
                }
                for snapshot in snapshots
            ],
        }

    def test_maps_ordered_financial_periods(self) -> None:
        self.assertEqual(
            [statement.reporting_period.label for statement in self.data.statements],
            ["2023", "2024", "2025", "2026Q3"],
        )
        self.assertEqual(self.data.time_frame, "2023 to 2026Q3")

    def test_period_files_reconcile_to_published_balance_sheet_totals(self) -> None:
        self.assertEqual(len(self.input_paths), 4)
        expected = {
            "2023": ("93592652122.38", "67296771086.53", "26295881035.85"),
            "2024": ("107839685095.13", "77943425823.11", "29896259272.02"),
            "2025": ("127214519738.62", "90308168667.69", "36906351070.93"),
            "2026Q3": ("150896057198.11", "111519567377.89", "39376489820.22"),
        }
        for path, statement in zip(self.input_paths, self.data.statements):
            asset_total, liability_total, equity_total = expected[statement.reporting_period.label]
            self.assertEqual(statement.assets.total_assets.amount, Decimal(asset_total))
            self.assertEqual(
                statement.liabilities.total_liabilities.amount,
                Decimal(liability_total),
            )
            self.assertEqual(statement.equity.total_equity.amount, Decimal(equity_total))
            self.assertTrue(statement.is_balanced)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"]["statement"], "Consolidated balance sheet")
            self.assertTrue(payload["source"]["url"].endswith(".PDF"))

    def test_multi_file_input_is_sorted_by_reporting_period(self) -> None:
        data = JSONFinancialStatementRepository(list(reversed(self.input_paths))).load()
        self.assertEqual(
            [statement.reporting_period.label for statement in data.statements],
            ["2023", "2024", "2025", "2026Q3"],
        )

    def test_calculates_time_frame_changes(self) -> None:
        self.assertEqual(
            self.result.first.total_assets.amount, Decimal("93592652122.38")
        )
        self.assertEqual(
            self.result.latest.total_assets.amount, Decimal("150896057198.11")
        )
        self.assertEqual(
            self.result.asset_change_percentage.quantize(Decimal("0.1")),
            Decimal("61.2"),
        )
        self.assertEqual(
            self.result.first.total_liabilities.amount,
            Decimal("67296771086.53"),
        )
        self.assertEqual(
            self.result.latest.total_liabilities.amount,
            Decimal("111519567377.89"),
        )
        self.assertEqual(self.result.latest.net_assets, Decimal("39376489820.22"))

    def test_generates_four_time_series_charts(self) -> None:
        charts = AssetCharts().generate(self.result)
        self.assertEqual(
            [chart.title for chart in charts],
            [
                "Assets, liabilities, and equity over time",
                "Reported equity trend",
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
        self.assertIn("61.2%", narrative)
        self.assertIn("CNY 150,896,057,198.11", narrative)

    def test_rejects_duplicate_period_labels(self) -> None:
        payload = self.bundled_payload()
        payload["periods"][1]["reporting_period"] = "2023"
        with self.assertRaisesRegex(DataValidationError, "unique"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_rejects_time_frame_boundary_mismatch(self) -> None:
        payload = self.bundled_payload()
        payload["time_frame"]["end"] = "2026"
        with self.assertRaisesRegex(DataValidationError, "must match"):
            JSONFinancialStatementRepository(self.write_json(payload)).load()

    def test_rejects_periods_out_of_order(self) -> None:
        payload = self.bundled_payload()
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
        generated = FinancialAnalysisApp().generate_time_frame_report(
            self.input_paths, output_path
        )
        self.assertEqual(generated, output_path.resolve())
        self.assertIn("Time-series analysis", output_path.read_text(encoding="utf-8"))

    def test_application_exposes_time_frame_analysis(self) -> None:
        result = FinancialAnalysisApp().analyze_time_frame(self.input_paths)
        self.assertIsInstance(result, TimeFrameAnalysisResult)
        self.assertEqual(result.data.time_frame, "2023 to 2026Q3")
        self.assertEqual(
            result.latest.total_assets.amount, Decimal("150896057198.11")
        )

    def test_time_frame_facade_accepts_one_period_file(self) -> None:
        result = FinancialAnalysisApp().analyze_time_frame(self.input_paths[0])
        self.assertIsInstance(result, TimeFrameAnalysisResult)
        self.assertEqual(result.data.time_frame, "2023")
        self.assertEqual(len(result.period_results), 1)
        self.assertEqual(result.asset_change, 0)
        self.assertEqual(result.liability_change, 0)

    def test_facade_exposes_only_time_frame_operations(self) -> None:
        app = FinancialAnalysisApp()
        self.assertTrue(callable(app.analyze_time_frame))
        self.assertTrue(callable(app.generate_time_frame_report))
        self.assertFalse(hasattr(app, "analyze_financial_data"))
        self.assertFalse(hasattr(app, "generate_financial_report"))
        self.assertFalse(hasattr(app, "generate_asset_report"))


class SchemaLibraryTests(unittest.TestCase):
    EXPECTED = {
        "cas/balance-sheet.schema.json": ("CAS_2019", "balance_sheet"),
        "cas/income-statement.schema.json": ("CAS_2019", "income_statement"),
        "cas/cash-flow-statement.schema.json": ("CAS_2019", "cash_flow_statement"),
        "ifrs-eu/balance-sheet.schema.json": ("IFRS_EU", "balance_sheet"),
        "ifrs-eu/income-statement.schema.json": ("IFRS_EU", "income_statement"),
        "ifrs-eu/cash-flow-statement.schema.json": ("IFRS_EU", "cash_flow_statement"),
        "us-gaap/balance-sheet.schema.json": ("US_GAAP_SEC", "balance_sheet"),
        "us-gaap/income-statement.schema.json": ("US_GAAP_SEC", "income_statement"),
        "us-gaap/cash-flow-statement.schema.json": ("US_GAAP_SEC", "cash_flow_statement"),
    }

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.schema_root = self.project_root / "schemas"

    @staticmethod
    def _walk(value: object):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from SchemaLibraryTests._walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from SchemaLibraryTests._walk(child)

    def test_catalog_lists_three_statements_for_three_profiles(self) -> None:
        catalog = json.loads(
            (self.schema_root / "catalog.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(catalog["profiles"]), 3)
        catalog_paths = {
            path
            for profile in catalog["profiles"]
            for path in profile["schemas"].values()
        }
        self.assertEqual(catalog_paths, set(self.EXPECTED))

    def test_all_standard_schemas_are_valid_json_with_local_refs(self) -> None:
        for relative_path, (profile, statement_type) in self.EXPECTED.items():
            path = self.schema_root / relative_path
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            constraints = schema["properties"]["schema"]["allOf"][1]["properties"]
            self.assertEqual(constraints["profile"]["const"], profile)
            self.assertEqual(
                constraints["statement_type"]["const"], statement_type
            )

            local_refs = {
                node["$ref"].split("#", 1)[0]
                for node in self._walk(schema)
                if "$ref" in node and not node["$ref"].startswith("#")
            }
            for reference in local_refs:
                self.assertTrue(
                    (path.parent / reference).resolve().is_file(),
                    f"Missing reference {reference} from {relative_path}",
                )

    def test_every_profile_allows_traceable_company_extensions(self) -> None:
        for relative_path in self.EXPECTED:
            schema = json.loads(
                (self.schema_root / relative_path).read_text(encoding="utf-8")
            )
            canonical_enums = [
                node["canonical_field"]["enum"]
                for node in self._walk(schema)
                if "canonical_field" in node
                and isinstance(node["canonical_field"], dict)
                and "enum" in node["canonical_field"]
            ]
            self.assertTrue(canonical_enums, relative_path)
            self.assertTrue(
                all("other" in values for values in canonical_enums), relative_path
            )

        common = json.loads(
            (self.schema_root / "common.schema.json").read_text(encoding="utf-8")
        )
        required = common["$defs"]["lineItem"]["required"]
        self.assertEqual(required, ["name", "amount", "source_field", "description"])

    def test_gotion_samples_identify_the_cas_balance_sheet_profile(self) -> None:
        for path in sorted((self.project_root / "sample_data").glob("gotion*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"]["profile"], "CAS_2019")
            self.assertEqual(payload["schema"]["statement_type"], "balance_sheet")
            self.assertEqual(
                payload["schema"]["presentation_basis"], "current_non_current"
            )


class IntegrationTests(TemporaryJSONMixin, unittest.TestCase):
    def test_real_period_input_maps_standard_and_additional_fields(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        data = JSONFinancialStatementRepository(
            project_root
            / "sample_data"
            / "gotion_high_tech_co_ltd_2025.json"
        ).load()
        self.assertEqual(
            data.statement.total_current_assets.amount, Decimal("53931020243.67")
        )
        self.assertEqual(
            data.statement.total_non_current_assets.amount, Decimal("73283499494.95")
        )
        self.assertEqual(data.statement.total_assets.amount, Decimal("127214519738.62"))
        self.assertEqual(
            data.statement.cash_and_cash_equivalents.amount,
            Decimal("16813185998.06"),
        )
        self.assertEqual(
            data.statement.additional_non_current_assets[0].name,
            "Other non-current financial assets",
        )
        self.assertEqual(
            data.liabilities.total_current_liabilities.amount,
            Decimal("66333699552.90"),
        )
        self.assertEqual(
            data.liabilities.total_non_current_liabilities.amount,
            Decimal("23974469114.79"),
        )
        self.assertEqual(
            data.liabilities.total_liabilities.amount, Decimal("90308168667.69")
        )
        self.assertEqual(data.equity.total_equity.amount, Decimal("36906351070.93"))
        self.assertEqual(data.balance_difference, Decimal("0.00"))
        self.assertTrue(data.is_balanced)
        self.assertEqual(data.assets.cash_and_cash_equivalents.amount, Decimal("16813185998.06"))
        cash_metric = next(
            item
            for item in AssetAnalysisService().analyze(data).all_asset_metrics
            if item.name == "Cash and cash equivalents"
        )
        self.assertEqual(cash_metric.source_field, "货币资金")
        self.assertIn("Source field 货币资金", cash_metric.description)
        self.assertEqual(data.company.ticker, "002074.SZ")

    def test_application_generates_complete_report(self) -> None:
        input_path = self.write_json(valid_payload())
        output_path = Path(self.temp_dir.name) / "report.html"
        generated = FinancialAnalysisApp().generate_time_frame_report(
            input_path, output_path
        )
        self.assertEqual(generated, output_path.resolve())
        html = output_path.read_text(encoding="utf-8")
        self.assertIn("Latest asset detail", html)
        self.assertIn("Latest liability detail", html)
        self.assertIn("Latest equity detail", html)
        self.assertIn("Time-series analysis", html)
        self.assertIn("<strong>Periods</strong> · 1", html)

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


class ThreeStatementWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.source_directory = self.project_root / "sample_data" / "three_statements"

    def test_retrieves_and_normalizes_every_statement_in_time_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = FinancialAnalysisApp().retrieve_three_statements(
                self.source_directory,
                temporary,
                company="Example Manufacturing Co., Ltd.",
                start_period="2024",
                end_period="2025",
                schema_profile="CAS_2019",
            )
            self.assertEqual(result.bundle.periods, ("2024", "2025"))
            self.assertEqual(len(result.statement_paths), 6)
            self.assertTrue(result.manifest_path.is_file())
            statement = json.loads(result.statement_paths[0].read_text(encoding="utf-8"))
            first_item = statement["assets"]["current"][0]
            self.assertEqual(first_item["canonical_field"], "cash_and_cash_equivalents")

            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["statement_count"], 6)
            self.assertEqual(manifest["time_frame"]["periods"], ["2024", "2025"])

    def test_retrieval_reports_an_incomplete_time_frame(self) -> None:
        query = StatementQuery(
            company="Example Manufacturing Co., Ltd.",
            start_period="2024",
            end_period="2026",
            schema_profile="CAS_2019",
        )
        with self.assertRaisesRegex(DataValidationError, "2026"):
            JSONStatementDirectoryRepository(self.source_directory).retrieve(query)

    def test_catalog_resolves_all_three_schema_files(self) -> None:
        catalog = SchemaCatalog()
        for statement_type in (
            "balance_sheet",
            "income_statement",
            "cash_flow_statement",
        ):
            self.assertTrue(catalog.schema_path("CAS_2019", statement_type).is_file())

    def test_run_directories_are_unique_and_below_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "output"
            first = create_run_directory(output, "unittest")
            second = create_run_directory(output, "unittest")
            self.assertNotEqual(first, second)
            self.assertEqual(first.parent, output.resolve())
            self.assertTrue(first.name.startswith("unittest-"))


class WebUITests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.manager = AnalysisTaskManager()
        self.server = create_server(
            "127.0.0.1",
            0,
            manager=self.manager,
            project_root=self.project_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def read_json(self, path: str) -> dict[str, object]:
        with urlopen(self.base_url + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_ui_serves_page_and_runs_normalization_task(self) -> None:
        with urlopen(self.base_url + "/", timeout=5) as response:
            page = response.read().decode("utf-8")
        self.assertIn("Financial analysis, on demand", page)
        config = self.read_json("/api/config")
        self.assertEqual(len(config["profiles"]), 3)

        payload = {
            "action": "normalize_statements",
            "company": "Example Manufacturing Co., Ltd.",
            "start_period": "2024",
            "end_period": "2025",
            "schema_profile": "CAS_2019",
            "source_directory": str(
                self.project_root / "sample_data" / "three_statements"
            ),
            "output_directory": self.temp_directory.name,
        }
        request = Request(
            self.base_url + "/api/tasks",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 202)
            task = json.loads(response.read().decode("utf-8"))

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            task = self.read_json(f"/api/tasks/{task['id']}")
            if task["status"] in {"succeeded", "failed"}:
                break
            time.sleep(0.05)
        self.assertEqual(task["status"], "succeeded", task["message"])
        self.assertEqual(len(task["artifacts"]), 7)
        with urlopen(
            self.base_url + f"/api/tasks/{task['id']}/artifacts/0", timeout=5
        ) as response:
            manifest = json.loads(response.read().decode("utf-8"))
        self.assertEqual(manifest["statement_count"], 6)


if __name__ == "__main__":
    unittest.main()
