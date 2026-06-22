"""Tests for scripts/research_framework/fin_charts.py

Covers:
    - ChartConfig dataclass
    - CHART_PRESETS completeness and structure
    - FinancialChartFactory class existence and method availability
"""

import pytest
import numpy as np
import pandas as pd


class TestChartConfig:
    """ChartConfig dataclass tests."""

    def test_default_values(self):
        from scripts.research_framework.fin_charts import ChartConfig

        cfg = ChartConfig()
        assert cfg.figsize == (8, 5.5)
        assert cfg.dpi == 300
        assert cfg.font_family == "Times New Roman"
        assert cfg.font_size == 10
        assert cfg.title_fontsize == 12
        assert cfg.label_fontsize == 10
        assert cfg.tick_fontsize == 9
        assert cfg.line_width == 1.5
        assert cfg.marker_size == 5.0
        assert cfg.grid_alpha == 0.3
        assert cfg.legend_fontsize == 9
        assert cfg.output_formats == ["pdf", "png"]
        assert cfg.style == "seaborn-v0_8-paper"
        assert cfg.color_palette == "colorblind"

    def test_custom_values(self):
        from scripts.research_framework.fin_charts import ChartConfig

        cfg = ChartConfig(figsize=(10, 6), dpi=150, font_family="Arial")
        assert cfg.figsize == (10, 6)
        assert cfg.dpi == 150
        assert cfg.font_family == "Arial"

    def test_chart_config_as_dict(self):
        from scripts.research_framework.fin_charts import ChartConfig

        cfg = ChartConfig()
        d = vars(cfg)
        assert "figsize" in d
        assert "dpi" in d
        assert "font_family" in d


class TestChartPresets:
    """CHART_PRESETS dictionary tests."""

    def test_presets_is_dict(self):
        from scripts.research_framework.fin_charts import CHART_PRESETS

        assert isinstance(CHART_PRESETS, dict)
        assert len(CHART_PRESETS) >= 5

    def test_known_chart_types_present(self):
        from scripts.research_framework.fin_charts import CHART_PRESETS

        known_types = [
            "parallel_trends",
            "psm_distribution",
            "correlation_heatmap",
            "descriptive_bar",
            "residual_qq",
            "residual_distribution",
            "placebo_distribution",
        ]
        for chart_type in known_types:
            assert chart_type in CHART_PRESETS, f"{chart_type} not in CHART_PRESETS"

    def test_each_preset_has_name(self):
        from scripts.research_framework.fin_charts import CHART_PRESETS

        for chart_type, preset in CHART_PRESETS.items():
            assert "name" in preset, f"{chart_type} missing 'name'"
            assert "required_cols" in preset, f"{chart_type} missing 'required_cols'"

    def test_preset_col_types(self):
        from scripts.research_framework.fin_charts import CHART_PRESETS

        for chart_type, preset in CHART_PRESETS.items():
            assert isinstance(preset.get("required_cols", []), list)
            assert isinstance(preset.get("optional_cols", []), list)

    def test_figsize_tuples(self):
        from scripts.research_framework.fin_charts import CHART_PRESETS

        for chart_type, preset in CHART_PRESETS.items():
            figsize = preset.get("figsize")
            if figsize is not None:
                assert isinstance(figsize, (tuple, list))
                assert len(figsize) == 2


class TestFinancialChartFactory:
    """FinancialChartFactory class interface tests."""

    def test_factory_class_exists(self):
        from scripts.research_framework.fin_charts import FinancialChartFactory
        assert FinancialChartFactory is not None

    def test_factory_has_plot_methods(self):
        from scripts.research_framework.fin_charts import FinancialChartFactory

        # Check class attributes/methods exist
        for method in [
            "plot_parallel_trends",
            "plot_residual_diagnostics",
            "plot_psm_distribution",
            "plot_heterogeneity",
            "plot_balance_table",
            "plot_robustness_summary",
        ]:
            assert hasattr(FinancialChartFactory, method), f"Missing method: {method}"

    def test_factory_instantiable(self):
        from scripts.research_framework.fin_charts import FinancialChartFactory

        # Just verify the class can be imported without error
        # (full instantiation tested separately to avoid matplotlib side-effects)
        assert callable(FinancialChartFactory)

    def test_factory_module_understood(self):
        from scripts.research_framework.fin_charts import FinancialChartFactory, CHART_PRESETS

        # Verify module exports are correct
        assert hasattr(FinancialChartFactory, "plot_parallel_trends")
        assert isinstance(CHART_PRESETS, dict)
