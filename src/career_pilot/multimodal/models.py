from typing import Literal

from pydantic import Field, model_validator

from career_pilot.models import StrictModel

ExtractionMethod = Literal["native_text", "ocr"]
SourceType = Literal["text", "markdown", "docx", "pdf", "image"]


class ExtractedPage(StrictModel):
    """Text and metadata extracted from one page."""

    page_number: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=200_000)
    extraction_method: ExtractionMethod


class ExtractedDocument(StrictModel):
    """A document converted into a unified extraction result."""

    filename: str = Field(min_length=1, max_length=255)
    source_path: str = Field(min_length=1, max_length=1_000)
    source_type: SourceType
    pages: list[ExtractedPage] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_page_order(self) -> "ExtractedDocument":
        actual_numbers = [
            page.page_number for page in self.pages
        ]

        if actual_numbers != sorted(set(actual_numbers)):
            raise ValueError(
                "页码必须严格递增且不能重复"
            )

        return self

    @property
    def content(self) -> str:
        return "\n\n".join(page.text for page in self.pages)