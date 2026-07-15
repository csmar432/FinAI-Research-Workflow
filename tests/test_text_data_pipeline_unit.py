"""Unit tests for scripts/core/text_data_pipeline.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def tdp():
    _p = str(SCRIPTS_DIR)
    if _p not in sys.path:
        sys.path.insert(0, _p)
    from scripts.core import text_data_pipeline as t
    yield t
    if _p in sys.path:
        sys.path.remove(_p)


class TestSentimentAnalyzer:
    def test_analyze_returns_dict(self, tdp):
        sa = tdp.SentimentAnalyzer()
        result = sa.analyze("This company has strong growth.")
        assert isinstance(result, dict)
        assert "sentiment_score" in result
        assert "sentiment_label" in result

    def test_analyze_positive_sentiment(self, tdp):
        sa = tdp.SentimentAnalyzer()
        result = sa.analyze("Excellent performance, strong growth, outstanding results.")
        assert result["sentiment_score"] >= 0

    def test_analyze_negative_sentiment(self, tdp):
        sa = tdp.SentimentAnalyzer()
        result = sa.analyze("Declining revenue, mounting losses, poor performance.")
        assert result["sentiment_score"] <= 0


class TestTextRecord:
    def test_text_record_all_required_fields(self, tdp):
        rec = tdp.TextRecord(
            source_type="annual_report",
            source_url="http://example.com",
            title="Annual Report 2024",
            content="Full text content here...",
            publish_date="2024-03-01",
            company="Example Corp",
            ts_code="000001.SZ",
            word_count=5000,
            extracted_entities=["Company A"],
            sentiment_scores={"overall": 0.5},
            key_disclosures=[],
            metadata={},
        )
        assert rec.company == "Example Corp"
        assert rec.word_count == 5000
        assert rec.sentiment_scores["overall"] == 0.5


class TestTextExtractor:
    def test_extract_dates(self, tdp):
        extractor = tdp.TextExtractor()
        dates = extractor.extract_dates("The report was published on March 15, 2024.")
        assert isinstance(dates, list)

    def test_extract_financial_numbers(self, tdp):
        extractor = tdp.TextExtractor()
        numbers = extractor.extract_financial_numbers(
            "Revenue was 100 billion yuan, with net profit of 10 billion."
        )
        assert isinstance(numbers, dict)

    def test_extract_key_metrics(self, tdp):
        extractor = tdp.TextExtractor()
        metrics = extractor.extract_key_metrics("ROE is 15% and ROA is 8%.")
        assert isinstance(metrics, dict)

    def test_extract_commitments(self, tdp):
        extractor = tdp.TextExtractor()
        commitments = extractor.extract_commitments(
            "The company promises to increase R&D spending by 20%."
        )
        assert isinstance(commitments, list)


class TestTextDataPipeline:
    def test_pipeline_init(self, tdp):
        pipeline = tdp.TextDataPipeline()
        assert pipeline.cache_dir is None
        assert hasattr(pipeline, "extractor")
        assert hasattr(pipeline, "sentiment")
        assert hasattr(pipeline, "scraper")

    def test_pipeline_init_with_cache(self, tdp):
        from pathlib import Path
        pipeline = tdp.TextDataPipeline(cache_dir="/tmp/cache")
        assert pipeline.cache_dir == Path("/tmp/cache")


class TestConstants:
    def test_positive_words_not_empty(self, tdp):
        assert len(tdp.POSITIVE_WORDS) > 0

    def test_negative_words_not_empty(self, tdp):
        assert len(tdp.NEGATIVE_WORDS) > 0

    def test_uncertainty_words_not_empty(self, tdp):
        assert len(tdp.UNCERTAINTY_WORDS) > 0

    def test_financial_mentions_not_empty(self, tdp):
        assert len(tdp.FINANCIAL_MENTIONS) > 0

    def test_text_source_enum(self, tdp):
        sources = list(tdp.TextSource)
        assert len(sources) >= 5
        assert tdp.TextSource.NEWS in sources
        assert tdp.TextSource.ANNUAL_REPORT in sources
        assert tdp.TextSource.QUARTERLY_REPORT in sources
