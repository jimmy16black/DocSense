from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CitationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    page_number: int = Field(..., alias="pageNumber", description="1-based page number")
    section_heading: str | None = Field(
        None, alias="sectionHeading", description="Section or clause header"
    )
    exact_quote: str = Field(
        ..., alias="exactQuote", description="Exact quotation from document text"
    )
    bounding_box: dict[str, Any] | None = Field(
        None, alias="boundingBox", description="Coordinates on page"
    )
