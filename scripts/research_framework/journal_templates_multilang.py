"""Multi-language journal templates for 论文-研报工作流.

Extends journal_templates.py with Japanese and German economics journals.

Supported journals:
    Japanese:
    - JPE: Journal of Political Economy
    - RES: Review of Economic Studies
    - JoMa: Journal of Econometrics

    German:
    - ZWiSt: Zeitschrift für Wirtschafts- und Sozialwissenschaften
    - JNS: Journal of the Japanese and International Economies

Usage:
    templates = get_multilang_templates()
    template = templates["JPE"]
    print(template.paper_class)
    print(template.sections)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TemplateStyle(str, Enum):
    ENGLISH = "english"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    GERMAN = "german"
    FRENCH = "french"


@dataclass
class JournalTemplate:
    """Extended journal template with multi-language support."""
    journal_code: str
    full_name: str
    style: TemplateStyle
    paper_class: str  # e.g., "article" for LaTeX

    # Structure
    sections: list[str]  # Ordered list of section names
    abstract_required: bool = True
    abstract_words: int = 150  # Max words for abstract

    # Word/page limits
    word_limit: int | None = None      # Main text (excl. refs/appendix)
    page_limit: int | None = None

    # Formatting
    font_size: str = "11pt"
    line_spacing: str = "onehalfspacing"
    margins: str = "1in"

    # Citation style
    citation_style: str = "authoryear"   # authoryear | numeric | chicago
    bibliography_command: str = "\\bibliography{refs}"

    # Section labels
    introduction_label: str = "1"
    appendix_label: str = "Appendix"
    references_label: str = "References"

    # Language-specific fields
    language: str = "english"            # Primary language
    second_language: str | None = None   # Optional second language (e.g., Chinese abstract in English paper)
    abstract_label: str = "Abstract"      # Label for abstract section (language-specific)

    # Japanese/German specific
    jEL_codes: list[str] = field(default_factory=list)  # JEL classification codes
    keywords_label: str = "Keywords"
    keywords_separator: str = "; "

    # Review process
    review_style: str = "single_blind"  # single_blind | double_blind | open
    resubmission_allowed: bool = True
    supplementary_online_label: str = "Online Appendix"

    # Tables and figures
    table_caption_above: bool = True
    figure_caption_above: bool = True
    table_width: str = "\\textwidth"
    figure_width: str = "\\textwidth"

    # Extra notes
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_code": self.journal_code,
            "full_name": self.full_name,
            "style": self.style.value,
            "paper_class": self.paper_class,
            "sections": self.sections,
            "word_limit": self.word_limit,
            "page_limit": self.page_limit,
            "citation_style": self.citation_style,
            "language": self.language,
            "jEL_codes": self.jEL_codes,
            "review_style": self.review_style,
        }

    def format_word_limit_note(self) -> str:
        """Return a human-readable word/page limit note."""
        notes = []
        if self.word_limit:
            notes.append(f"Word limit: {self.word_limit:,}")
        if self.page_limit:
            notes.append(f"Page limit: {self.page_limit}")
        if self.abstract_words:
            notes.append(f"Abstract: {self.abstract_words} words")
        return "; ".join(notes)


def get_multilang_templates() -> dict[str, JournalTemplate]:
    """Return all multi-language journal templates."""
    return {
        # ─── Japanese Journals ─────────────────────────────────────────────────
        "JPE": JournalTemplate(
            journal_code="JPE",
            full_name="Journal of Political Economy",
            style=TemplateStyle.JAPANESE,
            paper_class="article",
            sections=["Abstract", "1. Introduction", "2. Literature Review",
                      "3. Theoretical Framework", "4. Data and Identification Strategy",
                      "5. Results", "6. Robustness Checks", "7. Conclusion",
                      "Appendix", "References"],
            abstract_required=True,
            abstract_words=150,
            word_limit=15000,
            page_limit=None,
            font_size="11pt",
            line_spacing="onehalfspacing",
            citation_style="authoryear",
            bibliography_command="\\bibliography{refs}",
            jEL_codes=["C01", "C33", "O44", "Q56"],
            keywords_label="JEL Classification",
            keywords_separator="; ",
            review_style="double_blind",
            resubmission_allowed=True,
            table_caption_above=True,
            figure_caption_above=True,
            notes=[
                "Double-blind review",
                "JEL classification required (2-4 codes)",
                "Word limit: 15,000 (main text, excl. refs/appendix)",
            ],
        ),

        "RES": JournalTemplate(
            journal_code="RES",
            full_name="Review of Economic Studies",
            style=TemplateStyle.JAPANESE,
            paper_class="article",
            sections=["Abstract", "1. Introduction", "2. Model",
                      "3. Data", "4. Identification", "5. Results",
                      "6. Additional Results", "7. Conclusion",
                      "Supplementary Material", "References"],
            abstract_required=True,
            abstract_words=150,
            word_limit=None,
            page_limit=50,
            font_size="11pt",
            line_spacing="onehalfspacing",
            citation_style="authoryear",
            bibliography_command="\\bibliography{refs}",
            jEL_codes=["C01", "C33", "O44"],
            keywords_label="JEL Classification",
            review_style="double_blind",
            resubmission_allowed=False,  # RES does not allow resubmission
            table_caption_above=True,
            figure_caption_above=True,
            supplementary_online_label="Supplementary Material",
            notes=[
                "Double-blind review",
                "No resubmission allowed (one-shot)",
                "50-page limit (including tables, figures, references)",
                "Online appendix required for additional results",
            ],
        ),

        "JoMa": JournalTemplate(
            journal_code="JoMa",
            full_name="Journal of Econometrics",
            style=TemplateStyle.JAPANESE,
            paper_class="article",
            sections=["Abstract", "1. Introduction", "2. Methodology",
                      "3. Monte Carlo Study", "4. Empirical Application",
                      "5. Conclusion", "Technical Appendix",
                      "Supplementary Material", "References"],
            abstract_required=True,
            abstract_words=200,
            word_limit=None,
            page_limit=None,  # No strict page limit
            font_size="11pt",
            line_spacing="onehalfspacing",
            citation_style="authoryear",
            bibliography_command="\\bibliography{refs}",
            jEL_codes=["C01", "C13", "C15", "C22"],
            keywords_label="JEL Classification",
            review_style="single_blind",
            resubmission_allowed=True,
            table_caption_above=True,
            figure_caption_above=True,
            notes=[
                "Single-blind review",
                "Monte Carlo study required for new methods",
                "JEL codes: C (Econometrics) preferred",
                "Technical appendix for proofs",
            ],
        ),

        # ─── German Journals ──────────────────────────────────────────────────
        "ZWiSt": JournalTemplate(
            journal_code="ZWiSt",
            full_name="Zeitschrift für Wirtschafts- und Sozialwissenschaften",
            style=TemplateStyle.GERMAN,
            paper_class="article",
            language="german",
            second_language="english",
            sections=["Zusammenfassung", "1. Einleitung", "2. Literaturüberblick",
                      "3. Theoretischer Rahmen", "4. Empirische Strategie",
                      "5. Daten", "6. Ergebnisse", "7. Robustheit",
                      "8. Schlussfolgerungen", "Anhang", "Literatur"],
            abstract_required=True,
            abstract_words=200,
            abstract_label="Zusammenfassung",
            word_limit=12000,
            page_limit=None,
            font_size="11pt",
            line_spacing="onehalfspacing",
            citation_style="authoryear",
            bibliography_command="\\bibliography{literatur}",
            introduction_label="1",
            appendix_label="Anhang",
            references_label="Literatur",
            keywords_label="Schlüsselwörter",
            keywords_separator=", ",
            review_style="double_blind",
            resubmission_allowed=True,
            table_caption_above=True,
            figure_caption_above=True,
            notes=[
                "Double-blind review (ZWiSt)",
                "German-language paper with English abstract",
                "Word limit: 12,000 (main text)",
                "German and English keywords required",
                "Citation style: author-year (German economics standard)",
            ],
        ),

        "JNS": JournalTemplate(
            journal_code="JNS",
            full_name="Journal of the Japanese and International Economies",
            style=TemplateStyle.JAPANESE,
            paper_class="article",
            sections=["Abstract", "1. Introduction", "2. Related Literature",
                      "3. Theoretical Model / Empirical Strategy",
                      "4. Data", "5. Results", "6. Conclusion",
                      "Appendix", "References"],
            abstract_required=True,
            abstract_words=150,
            word_limit=None,
            page_limit=40,
            font_size="11pt",
            line_spacing="onehalfspacing",
            citation_style="authoryear",
            bibliography_command="\\bibliography{refs}",
            jEL_codes=["O53", "F43", "Q56", "E66"],
            keywords_label="JEL Classification",
            review_style="single_blind",
            resubmission_allowed=True,
            table_caption_above=True,
            figure_caption_above=True,
            notes=[
                "Single-blind review",
                "40-page limit (including all material)",
                "Focus on Japan and international economics",
                "JEL codes preferred: O (Economic Development), F (International Economics)",
            ],
        ),
    }


def get_template(journal_code: str) -> JournalTemplate | None:
    """Get a template by journal code (case-insensitive)."""
    templates = get_multilang_templates()
    return templates.get(journal_code.upper())


def list_multilang_templates() -> list[dict[str, Any]]:
    """List all multi-language templates."""
    templates = get_multilang_templates()
    return [t.to_dict() for t in templates.values()]


def format_latex_preamble(template: JournalTemplate) -> str:
    """Generate the LaTeX preamble for a multi-language template."""
    lines = [
        f"\\documentclass[{template.font_size}]{{article}}",
        "\\usepackage[authoryear, round]{natbib}",
        "\\usepackage{amsmath, amssymb, amsthm}",
        "\\usepackage{hyperref}",
        "\\usepackage{booktabs}",
        "\\usepackage{setspace}",
        f"\\setstretch{{{1.3 if template.line_spacing == 'onehalfspacing' else 1.0}}}",
        "\\usepackage[left=1in, right=1in, top=1in, bottom=1in]{geometry}",
        "",
        f"% {template.full_name} ({template.journal_code})",
        f"% Style: {template.style.value}",
        "",
        "\\begin{document}",
        "",
    ]

    # Abstract
    if template.abstract_required:
        abs_label = getattr(template, "abstract_label", "Abstract")
        lines.append(f"\\begin{{{abs_label.lower().replace(' ', '')}}}")
        lines.append(f"[{template.abstract_words} words]")
        lines.append("摘要内容...")
        lines.append(f"\\end{{{abs_label.lower().replace(' ', '')}}}")

    # Keywords
    lines.append("")
    if template.jEL_codes:
        lines.append(f"\\paragraph{{{template.keywords_label}}}: "
                     f"{template.keywords_separator.join(template.jEL_codes)}")

    # Section labels
    for section in template.sections:
        if section in ("Abstract", "Zusammenfassung"):
            continue
        lines.append(f"\\section{{{section}}}")

    lines.append("")
    lines.append("\\bibliographystyle{ecta}")
    lines.append(f"{template.bibliography_command}")

    return "\n".join(lines)


if __name__ == "__main__":
    templates = get_multilang_templates()
    print(f"Multi-language templates loaded: {len(templates)}")
    for code, t in templates.items():
        print(f"  {code}: {t.full_name} ({t.style.value})")
        print(f"    {t.format_word_limit_note()}")
        print(f"    Sections: {len(t.sections)}")
        print(f"    JEL: {t.jEL_codes}")

    # Test preamble generation
    print("\n" + "=" * 60)
    print("JPE LaTeX Preamble:")
    print("=" * 60)
    print(format_latex_preamble(get_multilang_templates()["JPE"])[:500] + "...")
