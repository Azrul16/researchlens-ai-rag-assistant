from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=100)
    top_k: int = Field(default=8, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Query cannot be blank")
        return value.strip()


class Citation(StrictModel):
    source_id: str = ""
    document_id: str
    document_title: str
    page_number: int
    chunk_id: str
    section_title: str | None
    excerpt: str
    score: float


class SearchOut(StrictModel):
    results: list[Citation]


class ConversationInput(StrictModel):
    title: str = Field(default="New research conversation", min_length=1, max_length=200)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: str
    sources: list[Citation] = Field(default_factory=list)
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class MessageInput(StrictModel):
    content: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("content")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


class GeneratedAnswer(StrictModel):
    answer: str
    source_ids: list[str]
    sufficient_evidence: bool


class AnswerOut(StrictModel):
    answer: str
    sources: list[Citation]
    sufficient_evidence: bool


class Finding(StrictModel):
    text: str
    source_ids: list[str]


class PaperAnalysis(StrictModel):
    title: str
    authors: list[str]
    research_problem: Finding
    objectives: list[Finding]
    methodology: Finding
    datasets: list[Finding]
    models: list[Finding]
    metrics: list[Finding]
    key_results: list[Finding]
    contributions: list[Finding]
    limitations: list[Finding]
    future_work: list[Finding]


class AnalysisOut(StrictModel):
    analysis: PaperAnalysis
    sources: list[Citation]
    context_complete: bool


class SummaryOut(StrictModel):
    summary: str
    sources: list[Citation]
    context_complete: bool


class CompareInput(StrictModel):
    document_ids: list[UUID] = Field(min_length=2, max_length=8)
    focus: str = Field(
        default="Compare methodologies, datasets, results and limitations.",
        min_length=1,
        max_length=1000,
    )

    @field_validator("document_ids")
    @classmethod
    def unique(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select distinct papers")
        return value


class ComparisonRow(StrictModel):
    document_id: str
    paper: str
    year: str
    objective: str
    approach: str
    dataset: str
    dataset_size: str
    preprocessing: str
    training_setup: str
    metrics: str
    key_result: str
    strength: str
    limitation: str
    computational_requirements: str
    source_ids: list[str]


class GeneratedComparison(StrictModel):
    rows: list[ComparisonRow]
    narrative: str
    comparable: bool
    caveats: list[str]
    source_ids: list[str]


class ComparisonOut(GeneratedComparison):
    sources: list[Citation]


class ProviderHealth(StrictModel):
    provider: Literal["groq", "gemini"]
    configured: bool
    reachable: bool | None
