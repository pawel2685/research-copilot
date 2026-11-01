"""Download and persist an arXiv title/abstract corpus (no full-text PDFs)."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    published: str
    url: str

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.abstract}"


def fetch_papers(query: str, max_results: int = 100) -> list[Paper]:
    """Fetch a bounded corpus, retaining versioned IDs for reproducibility."""
    import arxiv

    if not query.strip() or max_results < 1:
        raise ValueError("Provide a nonempty query and positive max_results")
    client = arxiv.Client(page_size=100, delay_seconds=3.0, num_retries=3)
    request = arxiv.Search(query=query, max_results=max_results,
                           sort_by=arxiv.SortCriterion.Relevance)
    papers = {}
    for result in client.results(request):
        paper = Paper(
            arxiv_id=result.get_short_id(),
            title=" ".join(result.title.split()),
            abstract=" ".join(result.summary.split()),
            authors=[author.name for author in result.authors],
            published=result.published.isoformat(),
            url=result.entry_id.replace("http://", "https://", 1),
        )
        # Only one version of a paper per API response.
        papers[re.sub(r"v\d+$", "", paper.arxiv_id)] = paper
    return list(papers.values())


def save_corpus(papers: list[Paper], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(asdict(p), ensure_ascii=False) + "\n"
                                 for p in papers), encoding="utf-8")
    temporary.replace(path)


def load_corpus(path: str | Path) -> list[Paper]:
    return [Paper(**json.loads(line)) for line in Path(path).read_text(
        encoding="utf-8").splitlines() if line.strip()]
