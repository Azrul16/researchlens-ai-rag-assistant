from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        if not value.strip():
            raise ValueError("Workspace name cannot be blank")
        return value.strip()


class WorkspaceOut(WorkspaceInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class WorkspacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def nonempty(cls, value):
        if value is None or not value.strip():
            raise ValueError("Workspace name cannot be blank")
        return value.strip()


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    original_filename: str
    title: str | None
    authors: list[str]
    abstract: str | None
    page_count: int
    file_size: int
    chunk_count: int
    processing_status: str
    processing_error: str | None
    created_at: datetime


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    chunk_index: int
    page_number: int
    section_title: str | None
    content: str
    token_count: int
