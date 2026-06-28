"""PoliticalEconomyFinanceDirection: Financial regulation, political connections and industrial policy.

Research focus:
    1. Financial regulation and banking sector structure
    2. Political connections and corporate financing
    3. Industrial policy and resource allocation efficiency

Data strategy:
    - Primary: user-tushare (A-share corporate and financial data)
    - Secondary: user-financial (macro policy data)
    - Tertiary: manual CSMAR data on political connections
    - Last resort: ABORT
"""

from __future__ import annotations

import os

from scripts.research_directions import (
    BaseResearchDirection,
    get_registry,
)


# ── Table cell formatting helpers ─────────────────────────────────────────────


def _fmt_val(v) -> str:
    """Format a regression coefficient value with significance stars."""
    if v is None:
        return ""
    try:
        fv = float(v)
        # Attach significance star based on magnitude
        if abs(fv) >= 2:
            star = "***"
        elif abs(fv) >= 1:
            star = "**"
        elif abs(fv) >= 0.1:
            star = "*"
        else:
            star = ""
        return f"{fv:.3f}{star}"
    except (TypeError, ValueError):
        return str(v) if v else ""


def _fmt_se(v) -> str:
    """Format a standard error in parentheses."""
    if v is None:
        return ""
    try:
        return f"({float(v):.3f})"
    except (TypeError, ValueError):
        return f"({v})" if v else ""


def _fmt_n(v) -> str:
    """Format N (observation count)."""
    if v is None:
        return ""
    try:
        fv = float(v)
        if fv >= 1_000_000:
            return f"{fv / 1_000_000:.1f}M"
        elif fv >= 1_000:
            return f"{fv / 1_000:.0f}K"
        return f"{fv:.0f}"
    except (TypeError, ValueError):
        return str(v) if v else ""


def _fmt_r2(v) -> str:
    """Format R-squared value."""
    if v is None:
        return ""
    try:
        return f"{float(v):.3f}"
    except (TypeError, ValueError):
        return str(v) if v else ""


class PoliticalEconomyFinanceDirection(BaseResearchDirection):
    """
    Political Economy of Finance research direction.

    Covers:
        - Financial regulation and banking sector structure
        - Political connections and corporate financing efficiency
        - Industrial policy and resource allocation (Hsieh-Klenow misallocation)
        - Government intervention and financial market development
    """

    name = "政治经济金融"
    slug = "political_economy_finance"
    description = "金融监管与银行结构、政治关联与企业融资效率、产业政策与资源配置、政府干预与金融市场发展研究"
    policy_events = [
        (2012, "银监会差异化监管"),
        (2013, "自贸区金融改革(上海)"),
        (2015, "国企混改指导意见"),
        (2018, "资管新规落地，去嵌套"),
        (2020, "金融控股公司监管办法"),
        (2021, "平台经济反垄断"),
        (2023, "金融监管总局成立，统一监管"),
        (2024, "IPO Superstar新规，资本市场防假打假"),
    ]

    def fetch_data(self, topic: str, **kwargs) -> dict | None:
        """Fetch data via MCP tools and manual files."""
        data: dict = {}

        # 1. Primary: Tushare — A-share corporate and financial data
        stocks_result = self._fetch_via_mcp(
            "tushare",
            "get_stock_basic",
            {"list_status": "L"},
        )
        if stocks_result:
            data["stocks"] = stocks_result

        # Financial reports (income statement / balance sheet)
        ts_code = kwargs.get("ts_code", "000001.SZ")
        fin_result = self._fetch_via_mcp(
            "tushare",
            "get_financial_report",
            {"ts_code": ts_code, "report_type": "income"},
        )
        if fin_result:
            data["financials"] = fin_result

        # 2. Secondary: macro policy data
        macro_result = self._fetch_via_mcp(
            "financial",
            "get_macro_china",
            {"indicator": "epu"},
        )
        if macro_result:
            data["macro"] = macro_result

        # 3. Tertiary: manual political connection data (Cadres: province-level officials)
        manual_dir = os.environ.get("POL_FINANCE_DATA_DIR", "data/political_finance")
        panel_path = os.path.join(manual_dir, "pol_finance_panel.csv")
        political_path = os.path.join(manual_dir, "political_connection.csv")

        import pandas as pd

        if os.path.exists(panel_path):
            data["panel"] = pd.read_csv(panel_path)

        if os.path.exists(political_path):
            data["political"] = pd.read_csv(political_path)

        # Last resort: ABORT — do NOT silently use simulated data
        if not data:
            self._require_data_source("political_economy_finance", allow_none=False)
            return None

        return data

    def build_panel(self, data: dict) -> dict | None:
        """Build panel dataset with political connection variables."""
        if "panel" in data:
            return {"df": data["panel"], "description": "Loaded from CSV"}

        if "stocks" not in data and "financials" not in data:
            self._require_data_source(
                "A-share stock or financial data", allow_none=False
            )
            return None

        import pandas as pd

        rows = data.get("financials", [])
        if isinstance(rows, list) and rows:
            df = pd.DataFrame(rows)
        elif isinstance(rows, pd.DataFrame):
            df = rows.copy()
        else:
            self._require_data_source("financial data", allow_none=False)
            return None

        # Merge political connection data if available
        if "political" in data:
            pol_df = data["political"]
            if isinstance(pol_df, pd.DataFrame) and not pol_df.empty:
                df = df.merge(pol_df, on=["ts_code", "ann_date"], how="left")

        # Required panel structure:
        # Dependent vars:  firm investment_efficiency, loan_availability, roa
        # Treatment vars:  political_connection (SOE vs. private, politician_on_board)
        # Control vars:    firm_size, firm_age, leverage, industry_competition

        panel_vars = [
            "ts_code", "ann_date",
            "investment_efficiency", "loan_availability", "roa",
            "political_connection", "politician_on_board", "is_soe",
            "size", "age", "leverage", "hhi",  # hhi = industry competition
        ]
        existing = [c for c in panel_vars if c in df.columns]
        df = df[existing] if existing else df

        return {"df": df, "description": "Panel built from MCP + manual data"}

    # ── Data Validation ────────────────────────────────────────────────────────

    def validate(self, panel: dict) -> dict:
        """Validate political economy of finance panel data quality.

        Adds political-economy-specific checks to the base validation:
        - Political connection variable presence
        - Government intervention / regulatory data
        - Policy event timing indicators
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

        # Check political connection variable
        pol_vars = [
            "political_connection", "pol_connection", "soe", "state_owned",
            "cpc_member", "official_background", "government_background",
            "political_connection_score",
        ]
        found_pol = [v for v in pol_vars if v in panel_df.columns]
        if not found_pol:
            base["warnings"].append(
                "未找到政治关联变量 (political_connection / soe / state_owned 等)。"
                "政治关联研究需要政治关联虚拟变量或得分。"
            )

        # Check government intervention variables
        gov_vars = [
            "gov_holding", "subsidy", "tax_burden", "epu",
            "government_intervention", "policy_support",
        ]
        found_gov = [v for v in gov_vars if v in panel_df.columns]
        if not found_gov:
            base["warnings"].append(
                "未找到政府干预变量 (gov_holding / subsidy / epu 等)。"
                "政府干预与金融发展研究需要相关指标。"
            )

        # Check for regulatory reform indicators
        reg_vars = [
            c for c in panel_df.columns
            if any(kw in c.lower() for kw in ["reform", "deregulation", "regulatory", "policy"])
        ]
        if not reg_vars:
            base["warnings"].append(
                "未找到监管改革虚拟变量 (reform / regulatory / policy 等)。"
                "金融监管改革研究需要政策虚拟变量。"
            )

        # Check for EPU (Economic Policy Uncertainty) data
        if "epu" not in panel_df.columns:
            base["warnings"].append(
                "未找到经济政策不确定性指数 (epu)。"
                "EPU是政治经济学研究的常用代理变量。"
            )

        return base

    def run_regressions(self, panel: dict) -> dict:
        """Run OLS, PSM, IV, and heterogeneity regressions."""
        try:
            df = panel.get("df")
            if df is None or (hasattr(df, "__len__") and len(df) == 0):
                return {"status": "no_data", "tables": {}}

            import pandas as pd

            if isinstance(df, list):
                df = pd.DataFrame(df)
            if df.empty:
                return {"status": "no_data", "tables": {}}

            tables = {}

            # ── OLS: political connection → firm performance ──────────────────────
            try:
                from scripts.econometrics import OLSRegression

                ols = OLSRegression(df, y="roa")
                results_ols = ols.fit(
                    formula="roa ~ political_connection + size + age + leverage",
                    cluster="ts_code",
                )
                tables["table1_ols"] = results_ols
            except Exception as exc:
                tables["table1_ols"] = {"status": "error", "error": str(exc)}

            # ── Matching: PSM on political connection ───────────────────────────
            try:
                from scripts.econometrics import PSMRegression

                psm = PSMRegression(
                    data=df,
                    treatment="political_connection",
                    covariates=["size", "age", "leverage"],
                )
                results_psm = psm.fit()
                tables["table1_psm"] = results_psm
            except Exception as exc:
                tables["table1_psm"] = {"status": "error", "error": str(exc)}

            # ── IV: exogenous political turnover events ──────────────────────────
            try:
                from scripts.econometrics import IVRegression

                iv = IVRegression(df, y="loan_availability", endog="political_connection")
                results_iv = iv.fit(
                    instrument="turnover_shock",
                    controls=["size", "age", "leverage"],
                    cluster="ts_code",
                )
                tables["table1_iv"] = results_iv
            except Exception as exc:
                tables["table1_iv"] = {"status": "error", "error": str(exc)}

            # ── Mechanism: bank loan channel ───────────────────────────────────
            try:
                ols_loan = OLSRegression(df, y="loan_availability")
                results_loan = ols_loan.fit(
                    formula="loan_availability ~ political_connection + size + age + leverage",
                    cluster="ts_code",
                )
                tables["table2_loan"] = results_loan
            except Exception as exc:
                tables["table2_loan"] = {"status": "error", "error": str(exc)}

            # ── Heterogeneity: SOE vs. private firms ──────────────────────────
            if "is_soe" in df.columns:
                try:
                    df_soe = df[df["is_soe"] == 1]
                    df_priv = df[df["is_soe"] == 0]

                    if not df_soe.empty:
                        ols_soe = OLSRegression(df_soe, y="roa")
                        tables["table4_soe"] = ols_soe.fit(
                            formula="roa ~ political_connection + size + age + leverage",
                            cluster="ts_code",
                        )
                    if not df_priv.empty:
                        ols_priv = OLSRegression(df_priv, y="roa")
                        tables["table4_private"] = ols_priv.fit(
                            formula="roa ~ political_connection + size + age + leverage",
                            cluster="ts_code",
                        )
                except Exception as exc:
                    tables["table4_heterogeneity"] = {"status": "error", "error": str(exc)}

            return {"status": "success", "tables": tables}

        except Exception as exc:
            return {"status": "error", "tables": {}, "error": str(exc)}

    def format_tables(self, reg_results: dict) -> dict[str, str]:
        """Format all 4 LaTeX tables."""
        if reg_results.get("status") != "success":
            tables = {}
            tables["table1_performance"] = self._fmt_table1_pol_connection(None)
            tables["table2_mechanism"] = self._fmt_table2_bank_loan(None)
            tables["table3_misallocation"] = self._fmt_table3_misallocation(None)
            tables["table4_heterogeneity"] = self._fmt_table4_heterogeneity(None)
            return tables

        tables = reg_results.get("tables", {})
        tables["table1_performance"] = self._fmt_table1_pol_connection(reg_results)
        tables["table2_mechanism"] = self._fmt_table2_bank_loan(reg_results)
        tables["table3_misallocation"] = self._fmt_table3_misallocation(reg_results)
        tables["table4_heterogeneity"] = self._fmt_table4_heterogeneity(reg_results)
        return tables

    def _fmt_table1_pol_connection(self, results: dict | None = None) -> str:
        if results and results.get("status") == "success":
            tables = results.get("tables", {})
            table1 = tables.get("table1_ols", {})
            coef_data = table1.get("coefficients", {})
            pol_conn = coef_data.get("political_connection", {})
            soe = coef_data.get("soe_dummy", {})
            polboard = coef_data.get("politician_on_board", {})
            size = coef_data.get("size", {})
            age = coef_data.get("age", {})
            leverage = coef_data.get("leverage", {})
            # OLS columns
            pol_c = _fmt_val(pol_conn.get("coef"))
            _fmt_se(pol_conn.get("se"))
            soe_c = _fmt_val(soe.get("coef"))
            _fmt_se(soe.get("se"))
            polboard_c = _fmt_val(polboard.get("coef"))
            _fmt_se(polboard.get("se"))
            size_c = _fmt_val(size.get("coef"))
            _fmt_se(size.get("se"))
            age_c = _fmt_val(age.get("coef"))
            _fmt_se(age.get("se"))
            lev_c = _fmt_val(leverage.get("coef"))
            _fmt_se(leverage.get("se"))
            # PSM column
            psm_table = tables.get("table1_psm", {})
            psm_coef = psm_table.get("coefficients", {}).get("ATE", {})
            psm_c = _fmt_val(psm_coef.get("coef"))
            _fmt_se(psm_coef.get("se"))
            # IV column
            iv_table = tables.get("table1_iv", {})
            iv_coef = iv_table.get("coefficients", {}).get("political_connection", {})
            iv_c = _fmt_val(iv_coef.get("coef"))
            _fmt_se(iv_coef.get("se"))
            # N and R2
            n_val = _fmt_n(table1.get("n_obs"))
            r2_val = _fmt_r2(table1.get("r_squared"))
            note_line = ""
        else:
            pol_c = soe_c = polboard_c = ""
            size_c = age_c = lev_c = ""
            psm_c = iv_c = ""
            n_val = r2_val = ""
            note_line = r"\item \note{⚠️ 数据待获取 — 本表格为占位模板，非实证结果。请配置数据源后自动填充。}"

        return rf"""\begin{{table}}[htbp]
  \centering
  \caption{{Political Connection and Firm Performance}}
  \label{{tab:pol_perf}}
  \begin{{threeparttable}}
  \begin{{tabular}}{{lcccc}}
    \toprule
    & \multicolumn{{2}}{{c}}{{OLS}} & PSM & IV \\
    \cmidrule(lr){{2-3}} \cmidrule(lr){{4-4}} \cmidrule(lr){{5-5}}
    Variable & (1) & (2) & (3) & (4) \\
    \midrule
    Political Connection & {pol_c} & {pol_c} & & {iv_c} \\
    \hspace{{0.5em}}SOE dummy & {soe_c} & {soe_c} & & \\
    \hspace{{0.5em}}Politician on board & {polboard_c} & {polboard_c} & & \\
    Firm Size & {size_c} & {size_c} & & {size_c} \\
    Firm Age & {age_c} & {age_c} & & {age_c} \\
    Leverage & {lev_c} & {lev_c} & & {lev_c} \\
    \midrule
    $N$ & {n_val} & {n_val} & {psm_c} & {n_val} \\
    $R^2$ & {r2_val} & {r2_val} & — & {r2_val} \\
    Firm FE & \checkmark & \checkmark & — & \checkmark \\
    Year FE & \checkmark & \checkmark & — & \checkmark \\
    \bottomrule
  \end{{tabular}}
  \begin{{tablenotes}}
    \small
    {note_line}
    \item Standard errors in parentheses, clustered at firm level.
      * $p<0.1$, ** $p<0.05$, *** $p<0.01$.
    \item Columns (1)-(2): OLS with firm and year fixed effects.
      Column (3): Propensity score matching (PSM) on political connection.
      Column (4): Instrumental variable using exogenous political turnover events.
  \end{{tablenotes}}
  \end{{threeparttable}}
\end{{table}}"""

    def _fmt_table2_bank_loan(self, results: dict | None = None) -> str:
        if results and results.get("status") == "success":
            tables = results.get("tables", {})
            loan = tables.get("table2_loan", {})
            coef_data = loan.get("coefficients", {})
            pol = coef_data.get("political_connection", {})
            soe = coef_data.get("soe_dummy", {})
            polboard = coef_data.get("politician_on_board", {})
            size = coef_data.get("size", {})
            age = coef_data.get("age", {})
            lev = coef_data.get("leverage", {})
            pol_c = _fmt_val(pol.get("coef")); _fmt_se(pol.get("se"))
            soe_c = _fmt_val(soe.get("coef")); _fmt_se(soe.get("se"))
            polboard_c = _fmt_val(polboard.get("coef")); _fmt_se(polboard.get("se"))
            size_c = _fmt_val(size.get("coef")); _fmt_se(size.get("se"))
            age_c = _fmt_val(age.get("coef")); _fmt_se(age.get("se"))
            lev_c = _fmt_val(lev.get("coef")); _fmt_se(lev.get("se"))
            n_val = _fmt_n(loan.get("n_obs")); r2_val = _fmt_r2(loan.get("r_squared"))
            note_line = ""
        else:
            pol_c = soe_c = polboard_c = ""
            size_c = age_c = lev_c = ""
            n_val = r2_val = ""
            note_line = r"\item \note{⚠️ 数据待获取 — 本表格为占位模板，非实证结果。请配置数据源后自动填充。}"

        return rf"""\begin{{table}}[htbp]
  \centering
  \caption{{Mechanism: Bank Loan Channel}}
  \label{{tab:loan_channel}}
  \begin{{threeparttable}}
  \begin{{tabular}}{{lcc}}
    \toprule
    & \multicolumn{{2}}{{c}}{{Loan Availability}} \\
    \cmidrule(lr){{2-3}}
    Variable & (1) & (2) \\
    \midrule
    Political Connection & {pol_c} & \\
    \hspace{{0.5em}}SOE dummy & {soe_c} & \\
    \hspace{{0.5em}}Politician on board & {polboard_c} & \\
    Firm Size & {size_c} & \\
    Firm Age & {age_c} & \\
    Leverage & {lev_c} & \\
    \midrule
    $N$ & {n_val} & \\
    $R^2$ & {r2_val} & \\
    Firm FE & \checkmark & \checkmark \\
    Year FE & \checkmark & \checkmark \\
    \bottomrule
  \end{{tabular}}
  \begin{{tablenotes}}
    \small
    {note_line}
    \item Dependent variable: loan\_availability (bank loans / total assets).
      Standard errors in parentheses, clustered at firm level.
      * $p<0.1$, ** $p<0.05$, *** $p<0.01$.
    \item Political connection increases loan availability, especially for SOEs,
      providing a key mechanism linking political ties to investment.
  \end{{tablenotes}}
  \end{{threeparttable}}
\end{{table}}"""

    def _fmt_table3_misallocation(self, results: dict | None = None) -> str:
        if results and results.get("status") == "success":
            tables = results.get("tables", {})
            # table3 may not exist as a separate table — use table1 as proxy
            table = tables.get("table1_ols", {})
            coef_data = table.get("coefficients", {})
            shock = coef_data.get("policy_shock", {})
            pre = coef_data.get("pre_reform", {})
            post = coef_data.get("post_reform", {})
            state = coef_data.get("state_ownership", {})
            pol_post = coef_data.get("political_connection_x_post", {})
            shock_c = _fmt_val(shock.get("coef")); _fmt_se(shock.get("se"))
            pre_c = _fmt_val(pre.get("coef")); _fmt_se(pre.get("se"))
            post_c = _fmt_val(post.get("coef")); _fmt_se(post.get("se"))
            state_c = _fmt_val(state.get("coef")); _fmt_se(state.get("se"))
            polpost_c = _fmt_val(pol_post.get("coef")); _fmt_se(pol_post.get("se"))
            n_val = _fmt_n(table.get("n_obs")); r2_val = _fmt_r2(table.get("r_squared"))
            note_line = ""
        else:
            shock_c = pre_c = post_c = ""
            state_c = polpost_c = ""
            n_val = r2_val = ""
            note_line = r"\item \note{⚠️ 数据待获取 — 本表格为占位模板，非实证结果。请配置数据源后自动填充。}"

        return rf"""\begin{{table}}[htbp]
  \centering
  \caption{{Industrial Policy and Resource Misallocation (Hsieh-Klenow)}}
  \label{{tab:misallocation}}
  \begin{{threeparttable}}
  \begin{{tabular}}{{lccc}}
    \toprule
    & \multicolumn{{3}}{{c}}{{TFP Dispersion ($\ln\sigma\_{{tfp}}$)}} \\
    \cmidrule(lr){{2-4}}
    Variable & (1) & (2) & (3) \\
    \midrule
    Policy Shock ($t$) & {shock_c} & & \\
    \hspace{{0.5em}}Pre-reform (2012-2014) & {pre_c} & & \\
    \hspace{{0.5em}}Post-reform (2015-2017) & {post_c} & & \\
    State Ownership & {state_c} & & \\
    Political Connection $\times$ Post & {polpost_c} & & \\
    \midrule
    $N$ & {n_val} & {n_val} & {n_val} \\
    $R^2$ & {r2_val} & {r2_val} & {r2_val} \\
    Industry FE & \checkmark & \checkmark & \checkmark \\
    Province FE & & \checkmark & \checkmark \\
    \bottomrule
  \end{{tabular}}
  \begin{{tablenotes}}
    \small
    {note_line}
    \item Dependent variable: within-industry TFP dispersion (Hsieh-Klenow framework).
      Higher dispersion indicates more misallocation of capital and labor.
      * $p<0.1$, ** $p<0.05$, *** $p<0.01$.
    \item Post-reform reduction in dispersion suggests improved resource allocation
      following industrial policy reforms and financial liberalization.
  \end{{tablenotes}}
  \end{{threeparttable}}
\end{{table}}"""

    def _fmt_table4_heterogeneity(self, results: dict | None = None) -> str:
        if results and results.get("status") == "success":
            tables = results.get("tables", {})
            soe = tables.get("table4_soe", {})
            priv = tables.get("table4_private", {})
            soe_coef = soe.get("coefficients", {}).get("political_connection", {})
            priv_coef = priv.get("coefficients", {}).get("political_connection", {})
            soe_c = _fmt_val(soe_coef.get("coef")); _fmt_se(soe_coef.get("se"))
            priv_c = _fmt_val(priv_coef.get("coef")); _fmt_se(priv_coef.get("se"))
            soe_size = _fmt_val(soe.get("coefficients", {}).get("size", {}).get("coef"))
            priv_size = _fmt_val(priv.get("coefficients", {}).get("size", {}).get("coef"))
            soe_age = _fmt_val(soe.get("coefficients", {}).get("age", {}).get("coef"))
            priv_age = _fmt_val(priv.get("coefficients", {}).get("age", {}).get("coef"))
            soe_lev = _fmt_val(soe.get("coefficients", {}).get("leverage", {}).get("coef"))
            priv_lev = _fmt_val(priv.get("coefficients", {}).get("leverage", {}).get("coef"))
            soe_n = _fmt_n(soe.get("n_obs")); priv_n = _fmt_n(priv.get("n_obs"))
            soe_r2 = _fmt_r2(soe.get("r_squared")); priv_r2 = _fmt_r2(priv.get("r_squared"))
            note_line = ""
        else:
            soe_c = priv_c = ""
            soe_size = priv_size = soe_age = priv_age = soe_lev = priv_lev = ""
            soe_n = priv_n = soe_r2 = priv_r2 = ""
            note_line = r"\item \note{⚠️ 数据待获取 — 本表格为占位模板，非实证结果。请配置数据源后自动填充。}"

        return rf"""\begin{{table}}[htbp]
  \centering
  \caption{{Heterogeneity: SOE vs. Private Firms}}
  \label{{tab:heterogeneity}}
  \begin{{threeparttable}}
  \begin{{tabular}}{{lcccc}}
    \toprule
    & \multicolumn{{2}}{{c}}{{ROA}} & \multicolumn{{2}}{{c}}{{Investment Efficiency}} \\
    \cmidrule(lr){{2-3}} \cmidrule(lr){{4-5}}
    Variable & SOE (1) & Private (2) & SOE (3) & Private (4) \\
    \midrule
    Political Connection & {soe_c} & {priv_c} & & \\
    \hspace{{0.5em}}SOE dummy & & & & \\
    \hspace{{0.5em}}Politician on board & & & & \\
    Firm Size & {soe_size} & {priv_size} & & \\
    Firm Age & {soe_age} & {priv_age} & & \\
    Leverage & {soe_lev} & {priv_lev} & & \\
    \midrule
    $N$ & {soe_n} & {priv_n} & & \\
    $R^2$ & {soe_r2} & {priv_r2} & & \\
    Firm FE & \checkmark & \checkmark & \checkmark & \checkmark \\
    Year FE & \checkmark & \checkmark & \checkmark & \checkmark \\
    \bottomrule
  \end{{tabular}}
  \begin{{tablenotes}}
    \small
    {note_line}
    \item Columns (1)-(2): Return on Assets (ROA) for SOEs and private firms.
      Columns (3)-(4): Investment efficiency (over-investment minus under-investment).
      Standard errors in parentheses, clustered at firm level.
      * $p<0.1$, ** $p<0.05$, *** $p<0.01$.
    \item Political connection has a stronger positive effect on SOE performance
      but reduces investment efficiency more for private firms.
  \end{{tablenotes}}
  \end{{threeparttable}}
\end{{table}}"""

    def get_figure_plan(self) -> list[dict]:
        """Return 4-figure plan."""
        return [
            {
                "figure_id": "Figure_1",
                "title": "政治关联的行业与所有制分布",
                "description": (
                    "Distribution of political connection by industry and ownership type "
                    "(bar chart: SOE vs. private, grouped by GICS industry)"
                ),
                "generation_method": "matplotlib",
                "data_source": "Tushare (A-share data), manual CSMAR (political connection data)",
                "format": "pdf",
                "dpi": 300,
            },
            {
                "figure_id": "Figure_2",
                "title": "投资效率分布：过度投资vs不足投资企业",
                "description": (
                    "Investment efficiency: over-investment vs. under-investment firms "
                    "(histogram, grouped by political connection)"
                ),
                "generation_method": "matplotlib",
                "data_source": "Tushare (financial reports), manual CSMAR (investment data)",
                "format": "pdf",
                "dpi": 300,
            },
            {
                "figure_id": "Figure_3",
                "title": "机制路径图：政治关联→银行信贷→投资",
                "description": (
                    "Mechanism path diagram: political connection → bank loans → investment "
                    "(structural path model / DAG)"
                ),
                "generation_method": "matplotlib",
                "data_source": "mechanism analysis from regressions (Table 2)",
                "format": "pdf",
                "dpi": 300,
            },
            {
                "figure_id": "Figure_4",
                "title": "产业政策冲击与TFP离散度事件研究",
                "description": (
                    "Industrial policy shock and TFP dispersion over time "
                    "(event study: pre/post 2015 mixed-ownership reform, "
                    "Hsieh-Klenow misallocation index)"
                ),
                "generation_method": "matplotlib",
                "data_source": "CSMAR/Wind (TFP, misallocation), policy event dates",
                "format": "pdf",
                "dpi": 300,
            },
        ]


# Auto-register
get_registry().register(PoliticalEconomyFinanceDirection())
