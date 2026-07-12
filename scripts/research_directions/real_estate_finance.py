"""RealEstateFinanceDirection: Housing finance, LTV, land finance and urban investment bonds.

Research focus:
    1. Housing price dynamics and monetary policy transmission
    2. Land finance and local government debt sustainability
    3. Property tax and housing market regulation

Data strategy:
    - Primary: user-financial (macro housing data)
    - Secondary: user-tushare (REIT and property developer financials)
    - Tertiary: manual NBSC/NRCMS data
    - Last resort: ABORT
"""

from __future__ import annotations

import logging
import os

from scripts.research_directions import (
    BaseResearchDirection,
    get_registry,
)

from scripts.core.data_warning_notifier import warn as _data_warn

logger = logging.getLogger(__name__)


class RealEstateFinanceDirection(BaseResearchDirection):
    """
    Real estate finance research direction.

    Covers:
        - Housing price dynamics and monetary policy transmission
        - Land finance and local government debt sustainability (城投债)
        - Property tax reform and housing market regulation
        - Three Red Lines policy (三道红线) and developer leverage
    """

    name = "房地产金融"
    slug = "real_estate_finance"
    description = (
        "住房金融与货币政策传导、土地财政与城投债务可持续性、"
        "房地产税改革与住房市场调控研究"
    )
    policy_events = [
        (2010, "国十一条，房地产调控"),
        (2013, "新国五条，限购限贷"),
        (2016, "930新政，因城施策"),
        (2018, "棚改货币化收紧"),
        (2020, "三道红线政策出台"),
        (2021, "土地出让金划转税务部门征收"),
        (2022, "金融16条支持房地产"),
        (2023, "认房不认贷政策调整"),
        (2024, "城中村改造和保障房建设提速"),
    ]

    def fetch_data(self, topic: str, **kwargs) -> dict | None:
        """Fetch data from MCP tools and manual sources.

        Priority:
            1. user-financial (housing price index, land transaction volume)
            2. user-tushare (property developer financials, REIT returns)
            3. Manual files: 70城房价数据, 城投债发行数据
            4. ABORT if no data
        """
        data: dict = {}

        # ── Primary: user-financial — macro housing data ────────────────────
        housing_result = self._fetch_via_mcp(
            "financial",
            "get_macro_china",
            {"indicator": "housing_price_index"},
        )
        if housing_result:
            data["housing_price"] = housing_result

        land_result = self._fetch_via_mcp(
            "financial",
            "get_macro_china",
            {"indicator": "land_transaction_volume"},
        )
        if land_result:
            data["land_volume"] = land_result

        # ── Secondary: user-tushare — property developer financials ───────────
        ts_result = self._fetch_via_mcp(
            "tushare",
            "get_financial_report",
            {
                "ts_code": kwargs.get("ts_code", "000001.SZ"),
                "report_type": "balance",
            },
        )
        if ts_result:
            data["developer_balance"] = ts_result

        reit_result = self._fetch_via_mcp(
            "tushare",
            "get_reit_info",
            {},
        )
        if reit_result:
            data["reit"] = reit_result

        # ── Tertiary: manual files ───────────────────────────────────────────
        manual_dirs = [
            os.environ.get("REAL_ESTATE_DATA_DIR", "data/real_estate"),
            "data/macro",
        ]
        for mdir in manual_dirs:
            panel_path = os.path.join(mdir, "housing_panel.csv")
            if os.path.exists(panel_path):
                import pandas as pd

                data["panel"] = pd.read_csv(panel_path)
                break
            cbond_path = os.path.join(mdir, "chengtou_bond.csv")
            if os.path.exists(cbond_path):
                import pandas as pd

                data["chengtou_bond"] = pd.read_csv(cbond_path)

        # ── Last resort: ABORT ───────────────────────────────────────────────
        if not data:
            self._require_data_source("real_estate_finance", allow_none=False)
            return None

        return data

    def build_panel(self, data: dict) -> dict | None:
        """Build panel dataset for real estate finance analysis.

        Constructs a city-year panel with:
            - Dependent: housing prices, land transaction volume,
              urban investment bond yield
            - Treatment: Three Red Lines × post-2020,
              property tax pilot × post-2011
            - Controls: GDP growth, population, mortgage rate, land supply
        """
        import pandas as pd

        if "panel" in data:
            return {"df": data["panel"], "description": "Loaded from CSV"}

        # Build from housing price data
        housing_df = data.get("housing_price")
        if housing_df is not None:
            if isinstance(housing_df, list):
                df = pd.DataFrame(housing_df)
            elif hasattr(housing_df, "to_frame"):
                df = housing_df.to_frame().reset_index()
            else:
                df = pd.DataFrame()

            if not df.empty and "city" in df.columns:
                df = self._add_treatment_variables(df)
                return {
                    "df": df,
                    "description": "Panel from user-financial housing price index",
                }

        self._require_data_source(
            "city-level housing panel", allow_none=False
        )
        return None

    def _add_treatment_variables(self, df) -> "pd.DataFrame":
        """Add Three Red Lines and property tax treatment indicators."""
        import pandas as pd

        # Ensure year column exists
        if "year" not in df.columns:
            if "date" in df.columns:
                df["year"] = pd.to_datetime(df["date"]).dt.year
            elif "date_str" in df.columns:
                df["year"] = df["date_str"].str[:4].astype(int)

        # Three Red Lines treatment: post-2020
        df["post_three_redlines"] = (df["year"] >= 2020).astype(int)

        # Property tax pilot (Shanghai/Chongqing since 2011)
        if "city" in df.columns:
            df["tax_pilot_city"] = df["city"].isin(
                ["上海", "重庆"]
            ).astype(int)
            df["post_property_tax"] = (
                (df["year"] >= 2011) & df["tax_pilot_city"]
            ).astype(int)
        else:
            df["post_property_tax"] = 0

        return df

    # ── Data Validation ────────────────────────────────────────────────────────

    def validate(self, panel: dict) -> dict:
        """Validate real estate finance panel data quality.

        Adds real-estate-finance-specific checks to the base validation:
        - Property tax / housing price variable presence
        - Land finance / urban investment bond data
        - RE developer financial variables
        """
        import pandas as pd

        base = super().validate(panel)
        if not base["valid"]:
            return base

        panel_df = panel.get("df")
        if panel_df is None:
            panel_df = panel.get("panel")
        if panel_df is None or not isinstance(panel_df, pd.DataFrame) or panel_df.empty:
            return base

        # Check property tax / housing price variable
        housing_vars = [
            "housing_price", "property_price", "house_price_index",
            "hp_index", "price_to_income", "ltv",
        ]
        found_housing = [v for v in housing_vars if v in panel_df.columns]
        if not found_housing:
            base["warnings"].append(
                "未找到房价/房产税变量 (housing_price / property_price / ltv 等)。"
                "住房金融研究需要房价或LTV等关键变量。"
            )

        # Check land finance / urban investment bond variable
        land_vars = ["land_revenue", "land_sale", "urban_invest_bond", "city_invest_debt"]
        found_land = [v for v in land_vars if v in panel_df.columns]
        if not found_land:
            base["warnings"].append(
                "未找到土地财政/城投债变量 (land_revenue / urban_invest_bond 等)。"
                "土地财政研究需要土地出让金或城投债数据。"
            )

        # Check RE developer financial variables
        dev_vars = ["leverage", "lev", "debt_ratio", "current_ratio", "quick_ratio"]
        found_dev = [v for v in dev_vars if v in panel_df.columns]
        if not found_dev:
            base["warnings"].append(
                "未找到房企财务变量 (leverage / lev / debt_ratio)。"
                "房地产开发商研究需要杠杆率和偿债能力指标。"
            )

        # Check for policy reform indicators (Three Red Lines / property tax)
        reform_vars = [
            c for c in panel_df.columns
            if any(kw in c.lower() for kw in ["red_line", "post", "treat", "reform", "policy"])
        ]
        if not reform_vars:
            base["warnings"].append(
                "未找到政策改革虚拟变量 (post / treat / reform 等)。"
                "三道红线(2020)和房产税改革需要政策前后虚拟变量。"
            )

        return base

    def run_regressions(self, panel: dict) -> dict:
        """Run econometric regressions for real estate finance.

        Methods:
            1. DID (Borusyak et al. 2024) for Three Red Lines effect
            2. RDD for housing price at policy threshold
            3. Event study for urban investment bond spreads
            4. Spatial regression for land price spillovers
        """
        try:
            import pandas as pd

            df = panel.get("df", [])
            if isinstance(df, list):
                df = pd.DataFrame(df)
            if not isinstance(df, pd.DataFrame) or df.empty:
                return {"status": "no_data", "tables": {}}

            results: dict = {"status": "success", "tables": {}}

            # ── 1. DID: Three Red Lines effect (Borusyak et al. 2024) ─────
            try:
                from scripts.research_framework.modern_did import (
                    BorusyakHullJaravelSpillover,
                )

                required_cols = {
                    "y": ["housing_price", "leverage_ratio", "land_volume"],
                    "treatment": "post_three_redlines",
                }
                if all(c in df.columns for c in required_cols["y"]):
                    did_model = BorusyakHullJaravelSpillover(
                        data=df,
                        outcome="housing_price",
                        treatment="post_three_redlines",
                        covariates=[
                            "gdp_growth",
                            "population",
                            "mortgage_rate",
                        ],
                    )
                    did_res = did_model.fit()
                    results["tables"]["table1_three_redlines"] = did_res
            except Exception as exc:
                logger.warning("Three Red Lines Borusyak DID failed: %s", exc)

            # ── 2. OLS DID (fallback) ────────────────────────────────────────
            if "table1_three_redlines" not in results.get("tables", {}):
                try:
                    from scripts.econometrics import DIDRegression

                    did_reg = DIDRegression(
                        data=df,
                        y="housing_price",
                        treatment="post_three_redlines",
                        post="post_three_redlines",
                        treated_groups=["treated"],
                        post_period="2020",
                    )
                    results["tables"]["table1_three_redlines"] = did_reg.fit(
                        cluster="city"
                    )
                except Exception as exc:
                    logger.warning("Three Red Lines OLS DID fallback failed: %s", exc)

            # ── 3. RDD for housing price at policy threshold ────────────────
            try:
                from scripts.research_framework.modern_did import (
                    RDDRegression,
                )

                if "leverage_ratio" in df.columns and "distance_threshold" in df.columns:
                    rdd = RDDRegression(
                        data=df,
                        outcome="housing_price",
                        running="leverage_ratio",
                        threshold=0.0,
                        bandwidth=0.05,
                    )
                    results["tables"]["table2_rdd"] = rdd.fit()
            except Exception as exc:
                logger.warning("Housing price RDD failed: %s", exc)

            # ── 4. Event study for urban investment bond spreads ──────────────
            if "chengtou_bond" in panel or "chengtou_bond" in (
                v
                for v in (panel.get("description", "") or "").split()
            ):
                results["tables"]["table3_event_study"] = self._event_study_placeholder()

            # ── 5. Spatial regression for land price spillovers ──────────────
            try:
                from scripts.econometrics_extended import SpatialRegression

                spatial_cols = ["land_price", "lat", "lon"]
                if all(c in df.columns for c in spatial_cols):
                    sp = SpatialRegression(
                        data=df,
                        y="land_price",
                        W_type="distance",
                        model_type="SDM",
                    )
                    results["tables"]["table4_spatial"] = sp.fit()
            except Exception as exc:
                logger.warning("Land price spatial regression failed: %s", exc)

            if not results["tables"]:
                return {"status": "no_valid_regression", "tables": {}}

            return results

        except ImportError as exc:
            _data_warn(
                category="research_direction",
                source="real_estate_finance",
                reason=f"依赖包缺失: {exc}",
                site="scripts/research_directions/real_estate_finance.py:371",
            )
            return {"status": "import_error", "tables": {}, "error": str(exc)}
        except Exception as exc:
            _data_warn(
                category="research_direction",
                source="real_estate_finance",
                reason=f"run_regressions 顶层异常: {exc}",
                site="scripts/research_directions/real_estate_finance.py:373",
            )
            return {"status": "error", "tables": {}, "error": str(exc)}

    def _event_study_placeholder(self) -> dict:
        """Placeholder event study result for urban investment bonds."""
        return {
            "caption": "Event Study: Urban Investment Bond Spread Around Policy Announcements",
            "notes": "Event window: [-10, +10] trading days. "
            "Robust standard errors clustered at bond level.",
        }

    def format_tables(self, reg_results: dict) -> dict[str, str]:
        """Format regression results as 4 LaTeX tables.

        Table 1: Three Red Lines and property developer leverage
        Table 2: Land finance and local fiscal sustainability
        Table 3: Urban investment bond spread determinants
        Table 4: Spatial spillover effects
        """
        tables: dict[str, str] = {}

        if reg_results.get("status") not in ("success", "no_valid_regression"):
            return tables

        # ── Table 1: Three Red Lines ───────────────────────────────────────
        tables["table1_three_redlines"] = self._table1_three_redlines()

        # ── Table 2: Land finance ───────────────────────────────────────────
        tables["table2_land_finance"] = self._table2_land_finance()

        # ── Table 3: Urban investment bond spreads ──────────────────────────
        tables["table3_chengtou_bond"] = self._table3_chengtou_bond()

        # ── Table 4: Spatial spillovers ────────────────────────────────────
        tables["table4_spatial"] = self._table4_spatial()

        return tables

    def _table1_three_redlines(self) -> str:
        return r"""\begin{table}[htbp]
  \centering
  \caption{三道红线政策与企业杠杆率：双重差分估计}
  \label{tab:three_redlines}
  \begin{tabular}{lcccc}
    \hline\hline
    & (1) & (2) & (3) & (4) \\
    Variable & 全样本 & 一线 & 二线 & 三四线 \\
    \hline
    DID × post-2020 & \\\\
    \hspace{0.5em} × 高负债组 & \\\\
    \hspace{0.5em} × 民营房企 & \\\\
    \hline
    GDP增速 & & & & \\
    人口增速 & & & & \\
    按揭利率 & & & & \\
    \hline
    $N$ & \\\\
    $R^2$ & \\\\
    城市固定效应 & \checkmark & \checkmark & \checkmark & \checkmark \\
    年份固定效应 & \checkmark & \checkmark & \checkmark & \checkmark \\
    \hline
    \midrule
    \multicolumn{4}{l}{\textit{⚠️ 数据待获取 — 占位模板，非实证结果}} \\
    \hline
    \hline
  \end{tabular}
  \note{被解释变量：剔除预收款后资产负债率（\%）。DID为三道红线政策处理效应。
    控制变量：GDP增速、人口增速、5年期LPR。
    标准误聚类到城市层面。* $p<0.1$, ** $p<0.05$, *** $p<0.01$。}
\end{table}"""

    def _table2_land_finance(self) -> str:
        return r"""\begin{table}[htbp]
  \centering
  \caption{土地财政与地方财政可持续性}
  \label{tab:land_finance}
  \begin{tabular}{lccc}
    \hline\hline
    & (1) & (2) & (3) \\
    Variable & 土地出让收入 & 地方政府综合财力 & 城投有息债务 \\
    \hline
    土地成交面积 & \\\\
    \hspace{0.5em} × 后2018期 & \\\\
    \hline
    房地产开发投资 & \\\\
    \hline
    土地流拍率 & \\\\
    \hline
    $N$ & \\\\
    $R^2$ & \\\\
    城市固定效应 & \checkmark & \checkmark & \checkmark \\
    年份固定效应 & \checkmark & \checkmark & \checkmark \\
    \hline
    \midrule
    \multicolumn{3}{l}{\textit{⚠️ 数据待获取 — 占位模板，非实证结果}} \\
    \hline
    \hline
  \end{tabular}
  \note{被解释变量分别为：土地出让收入（亿元）、地方政府综合财力指数、城投平台有息债务余额（亿元）。
    标准误聚类到省份层面。* $p<0.1$, ** $p<0.05$, *** $p<0.01$。}
\end{table}"""

    def _table3_chengtou_bond(self) -> str:
        return r"""\begin{table}[htbp]
  \centering
  \caption{城投债信用利差决定因素}
  \label{tab:chengtou_bond}
  \begin{tabular}{lcccc}
    \hline\hline
    & (1) & (2) & (3) & (4) \\
    Variable & 全样本 & AAA & AA+ & AA \\
    \hline
    地方财政缺口 & \\\\
    土地成交溢价率 & \\\\
    隐性债务规模 & \\\\
    城投平台有息债务/资产 & \\\\
    主体信用评级(数字) & \\\\
    债券期限(年) & \\\\
    \hline
    $N$ & \\\\
    $R^2$ & \\\\
    年份固定效应 & \checkmark & \checkmark & \checkmark & \checkmark \\
    省份固定效应 & \checkmark & \checkmark & \checkmark & \checkmark \\
    \hline
    \midrule
    \multicolumn{4}{l}{\textit{⚠️ 数据待获取 — 占位模板，非实证结果}} \\
    \hline
    \hline
  \end{tabular}
  \note{被解释变量：城投债信用利差（bp）。数据来源：Wind。
    样本期间：2015—2024。标准误在债券层面聚类。* $p<0.1$, ** $p<0.05$, *** $p<0.01$。}
\end{table}"""

    def _table4_spatial(self) -> str:
        return r"""\begin{table}[htbp]
  \centering
  \caption{城市住房价格空间溢出效应}
  \label{tab:spatial_spillover}
  \begin{tabular}{lccc}
    \hline\hline
    & (1) & (2) & (3) \\
    Variable & SDM & SAR & SEM \\
    \hline
    直接效应：本市影响因素 & & & \\
    \hspace{0.5em} 经济基本面 & \\\\
    \hspace{0.5em} 人口净流入 & \\\\
    \hspace{0.5em} 土地供应 & \\\\
    \hline
    间接效应（溢出）：邻城影响 & & & \\
    \hspace{0.5em} 邻城经济基本面 & \\\\
    \hspace{0.5em} 邻城人口净流入 & \\\\
    \hline
    空间自相关（$\rho$） & \\\\
    \hline
    $N$ & \\\\
    $R^2$ & \\\\
    Log-Likelihood & \\\\
    \hline
    \midrule
    \multicolumn{3}{l}{\textit{⚠️ 数据待获取 — 占位模板，非实证结果}} \\
    \hline
    \hline
  \end{tabular}
  \note{SDM：空间杜宾模型；SAR：空间自回归模型；SEM：空间误差模型。
    空间权重矩阵：基于城市间地理距离（km）的反距离矩阵。
    控制变量：GDP增速、常住人口增速、房地产开发投资增速。
    * $p<0.1$, ** $p<0.05$, *** $p<0.01$。}
\end{table}"""

    def get_figure_plan(self) -> list[dict]:
        """Return 4-figure plan for the real estate finance manuscript."""
        return [
            {
                "figure_id": "Figure_1",
                "title": "70城房价指数走势（2010–2024）",
                "description": (
                    "70城房价指数走势（2010—2024）："
                    "分城市层级（一线/二线/三四线）展示同比涨幅，"
                    "标注三道红线（2020）、认房不认贷（2023）等政策节点"
                ),
                "generation_method": "matplotlib",
                "data_source": "user-financial (housing_price_index), manual 70城数据",
                "format": "pdf",
                "dpi": 300,
                "style": "line_chart_with_annotations",
            },
            {
                "figure_id": "Figure_2",
                "title": "城投债信用利差事件研究",
                "description": (
                    "事件研究：政策公告日前后台投债信用利差变动"
                    "（事件窗口[-30, +30]天，横轴为相对天数，纵轴为累积异常利差）"
                ),
                "generation_method": "matplotlib",
                "data_source": "城投债发行数据 (Wind/手动)",
                "format": "pdf",
                "dpi": 300,
                "style": "event_study_with_ci",
            },
            {
                "figure_id": "Figure_3",
                "title": "土地出让收入与城投债信用利差散点图（2015–2024）",
                "description": (
                    "土地出让收入与城投债信用利差散点图（2015-2024）: "
                    "横轴为土地出让收入增速，纵轴为城投债信用利差（bp），"
                    "按省份着色，含线性趋势线"
                ),
                "generation_method": "matplotlib",
                "data_source": "data/real_estate/ (manual), Wind",
                "format": "pdf",
                "dpi": 300,
                "style": "scatter_with_trend",
            },
            {
                "figure_id": "Figure_4",
                "title": "城市住房价格空间相关性地图（Moran I/LISA）",
                "description": (
                    "城市层面住房价格空间相关性地图（Moran I 散点图/LISA）: "
                    "展示高-高、低-低、高-低、低-高聚类城市分布，"
                    "底图为省份边界"
                ),
                "generation_method": "matplotlib+geopandas",
                "data_source": "70城房价数据+城市经纬度坐标",
                "format": "pdf",
                "dpi": 300,
                "style": "choropleth_moran_scatter",
            },
        ]


# Auto-register
get_registry().register(RealEstateFinanceDirection())
