from typing import List, Optional

from pydantic import BaseModel, Field


class PageRecord(BaseModel):
    page_number: int
    text: str
    document_type: Optional[str] = None
    date_of_service: Optional[str] = Field(
        default=None, description="YYYY-MM-DD when known"
    )


class PagesCorpus(BaseModel):
    case_id: str = "sample-10p"
    date_of_loss: str = "2023-04-13"
    pages: List[PageRecord]


class OrthoMetric(BaseModel):
    date_of_service: str = Field(description="YYYY-MM-DD or unknown")
    provider: str = ""
    metric_type: str = Field(description="Flexion, Abduction, MMT, etc.")
    value: str = Field(description="Numerical value with units")
    flagged_finding: bool = False
    source_page: int


class OrthoExtractionResult(BaseModel):
    metrics: List[OrthoMetric] = Field(default_factory=list)


class NeuroVisualFinding(BaseModel):
    date_of_service: str = "unknown"
    finding_type: str = Field(description="VEP, Saccades, Reading Fluency, etc.")
    result_summary: str
    grade_level_equivalent: Optional[float] = None
    source_page: int


class NeuroExtractionResult(BaseModel):
    findings: List[NeuroVisualFinding] = Field(default_factory=list)


class BillingLine(BaseModel):
    date_of_service: str = "unknown"
    cpt_code: Optional[str] = None
    icd10_code: Optional[str] = None
    description: str = ""
    billed_amount: Optional[str] = None
    adjustment: Optional[str] = None
    source_page: int


class BillingExtractionResult(BaseModel):
    lines: List[BillingLine] = Field(default_factory=list)


class BaselineFinding(BaseModel):
    date_of_service: str = "unknown"
    condition_or_finding: str
    notes: str = ""
    source_page: int


class BaselineExtractionResult(BaseModel):
    findings: List[BaselineFinding] = Field(default_factory=list)


class SynthesisSection(BaseModel):
    title: str
    body_markdown: str


class SynthesisResult(BaseModel):
    sections: List[SynthesisSection] = Field(default_factory=list)


class AuditorVerdict(BaseModel):
    pass_: bool = Field(validation_alias="pass", serialization_alias="pass")
    failures: List[str] = Field(default_factory=list)
    suggested_fixes: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
