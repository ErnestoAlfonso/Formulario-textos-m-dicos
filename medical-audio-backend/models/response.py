from pydantic import BaseModel, Field
from typing import Optional


class AnswerItem(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    selected_codes: list[str] = Field(default_factory=list)
    selected_labels: list[str] = Field(default_factory=list)
    free_text: Optional[str] = None


class ModuleAnswers(BaseModel):
    answers: list[AnswerItem] = Field(default_factory=list)


class Metadata(BaseModel):
    transcription_time_seconds: float = 0
    extraction_time_seconds: float = 0
    total_time_seconds: float = 0
    questions_total: int = 0
    questions_answered: int = 0
    sections_with_data: int = 0


class ProcessResponse(BaseModel):
    status: str
    transcription: str = ""
    clinical_summary: str = ""
    history: ModuleAnswers = Field(default_factory=ModuleAnswers)
    exam: ModuleAnswers = Field(default_factory=ModuleAnswers)
    datos_adicionales: list[str] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=Metadata)
