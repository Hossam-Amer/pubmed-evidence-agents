from pydantic import BaseModel, model_validator
from typing import Literal, Optional


class PICOQuery(BaseModel):
    P: str
    I: str
    C: Optional[str] = None
    O: str
    queries: list[str]


class Chunk(BaseModel):
    pmid: str
    title: str
    year: Optional[int] = None
    text: str
    score: float = 0.0


class GeneratorOutput(BaseModel):
    answer: str
    citations: list[dict]
    confidence: str  # "high" | "medium" | "low"


class VerifierOutput(BaseModel):
    verdict: Literal["pass", "fix", "error"]
    unsupported_claims: list[str]
    suggested_corrections: list[str]
    error: Optional[str] = None

    @model_validator(mode="after")
    def validate_verdict_consistency(self):
        if self.verdict == "pass" and self.unsupported_claims:
            raise ValueError("pass verdict cannot contain unsupported claims")
        if self.verdict == "fix" and not self.unsupported_claims:
            raise ValueError("fix verdict must identify at least one unsupported claim")
        if self.verdict == "error" and not self.error:
            raise ValueError("error verdict must include an error message")
        return self


class PipelineOutput(BaseModel):
    answer: str
    citations: list[dict]
    confidence: str
    evidence_trace: dict
    debug_log: list[dict] = []  # list of {step, message, elapsed_ms, level}
