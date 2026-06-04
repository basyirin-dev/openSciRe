from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class RetractionStatus(StrEnum):
    unchecked = "unchecked"
    retracted = "retracted"
    corrected = "corrected"
    expression_of_concern = "expression_of_concern"
    concern_raised = "concern_raised"
    unknown = "unknown"


class RetractionSource(StrEnum):
    pubmed = "pubmed"
    crossref = "crossref"
    pubpeer = "pubpeer"
    openalex = "openalex"


class RetractionRecord(BaseModel):
    identifier: str
    retraction_status: RetractionStatus = RetractionStatus.unchecked
    source: RetractionSource
    detected_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()
    notice_text: str = ""
    notice_url: str = ""
    reason: str = ""
    details: dict[str, Any] = {}
