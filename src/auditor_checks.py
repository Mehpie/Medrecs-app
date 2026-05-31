import re
from typing import Any, Dict, List, Set

CITATION_RE = re.compile(r"\[src\.\s*Pg\.\s*(\d+)\]", re.IGNORECASE)


def extract_cited_pages(markdown: str) -> List[int]:
    return [int(m) for m in CITATION_RE.findall(markdown)]


def all_extraction_source_pages(extractions: Dict[str, Any]) -> Set[int]:
    pages: Set[int] = set()
    for metric in extractions.get("ortho", {}).get("metrics", []):
        pages.add(int(metric["source_page"]))
    for finding in extractions.get("neuro", {}).get("findings", []):
        pages.add(int(finding["source_page"]))
    for line in extractions.get("billing", {}).get("lines", []):
        pages.add(int(line["source_page"]))
    for finding in extractions.get("baseline", {}).get("findings", []):
        pages.add(int(finding["source_page"]))
    return pages


def deterministic_audit(draft: str, extractions: Dict[str, Any]) -> List[str]:
    failures: List[str] = []
    cited = extract_cited_pages(draft)
    if not cited:
        failures.append("No [src. Pg. N] citations found in draft.")
        return failures

    allowed = all_extraction_source_pages(extractions)
    for pg in set(cited):
        if pg not in allowed:
            failures.append(
                f"Citation [src. Pg. {pg}] references a page with no extraction records."
            )

    all_values: List[str] = []
    for metric in extractions.get("ortho", {}).get("metrics", []):
        all_values.append(str(metric.get("value", "")))
    for finding in extractions.get("neuro", {}).get("findings", []):
        all_values.append(str(finding.get("result_summary", "")))
    for line in extractions.get("billing", {}).get("lines", []):
        for key in ("billed_amount", "cpt_code", "icd10_code"):
            if line.get(key):
                all_values.append(str(line[key]))

    numbers_in_draft = re.findall(r"\d+(?:\.\d+)?", draft)
    for num in numbers_in_draft:
        if num in ("2023", "2024", "2025", "13", "04"):
            continue
        if not any(num in v for v in all_values if v):
            failures.append(
                f"Numeric value '{num}' in draft may not appear in extraction records."
            )
            break

    return failures
