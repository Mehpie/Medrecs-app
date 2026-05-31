import json
from pathlib import Path
from typing import Iterator, List, Optional

from src.schemas import PageRecord, PagesCorpus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data" / "input" / "pages.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"


def load_corpus(path: Optional[Path] = None) -> PagesCorpus:
    path = path or DEFAULT_INPUT
    if not path.exists():
        raise FileNotFoundError(
            f"Missing pages file: {path}\n"
            "Copy your 10-page JSON to data/input/pages.json"
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        raw = {"case_id": "sample-10p", "date_of_loss": "2023-04-13", "pages": raw}
    return PagesCorpus.model_validate(raw)


def sort_pages_chronologically(pages: List[PageRecord]) -> List[PageRecord]:
    dated = [p for p in pages if p.date_of_service]
    undated = [p for p in pages if not p.date_of_service]
    dated.sort(key=lambda p: p.date_of_service or "")
    undated.sort(key=lambda p: p.page_number)
    return dated + undated


def iter_pages(
    corpus: PagesCorpus,
    page_filter: Optional[List[int]] = None,
) -> Iterator[PageRecord]:
    pages = sort_pages_chronologically(corpus.pages)
    if page_filter is not None:
        allowed = set(page_filter)
        pages = [p for p in pages if p.page_number in allowed]
    yield from pages


def keyword_flags(text: str, keywords: List[str]) -> List[str]:
    lower = text.lower()
    return [kw for kw in keywords if kw.lower() in lower]


INSPECTION_KEYWORDS = [
    "range of motion",
    "rom",
    "mmt",
    "flexion",
    "vep",
    "visual evoked",
    "cpt",
    "icd",
    "diabetes",
    "long covid",
    "hawkins",
    "spurling",
]
