from context.compression import compress
from contracts import Chunk, CompressFn, Report, RunConfig


def test_chunk_defaults():
    chunk = Chunk(paper_id="2005.11401", text="some text")
    assert chunk.score == 0.0
    assert chunk.source_url == ""


def test_report_defaults_to_unverified():
    report = Report(question="q", markdown="# answer")
    assert report.sources == []
    assert report.verified is False


def test_report_sources_are_not_shared_between_instances():
    first = Report(question="a", markdown="")
    second = Report(question="b", markdown="")
    first.sources.append("2005.11401")
    assert second.sources == []


def test_run_config_defaults():
    cfg = RunConfig()
    assert cfg.use_planner is True
    assert cfg.use_critic is True
    assert cfg.hybrid is True
    assert cfg.compress_budget_words == 3000
    assert cfg.time_budget_s == 90.0


def test_run_config_allows_disabling_compression():
    assert RunConfig(compress_budget_words=None).compress_budget_words is None


def test_real_compress_fits_the_contract():
    fn: CompressFn = compress
    assert fn(["one two three"], 2) == ["one two"]