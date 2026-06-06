from pydantic import BaseModel, Field


class ContextWindowConfig(BaseModel):
    model: str = ""
    max_context_tokens: int = 0
    reserved_output_tokens: int = 1024
    min_chunk_tokens: int = 50
    compression_strategy: str = "truncate"
    overflow_strategy: str = "drop"
    format_style: str = "structured"
    include_citation_context: bool = False


class TokenBudget(BaseModel):
    capacity: int = 4096
    reserved_output: int = 1024
    available: int = 3072
    used: int = 0
    remaining: int = 3072


class ContextItem(BaseModel):
    id: str = ""
    text: str = ""
    token_count: int = 0
    score: float = 0.0
    section: str = ""
    document_id: str = ""
    rank: int = 0
    status: str = "kept"


class OverflowReport(BaseModel):
    total_items: int = 0
    kept: int = 0
    truncated: int = 0
    summarized: int = 0
    dropped: int = 0
    total_overflow_tokens: int = 0


class ContextPackage(BaseModel):
    model: str = ""
    budget: TokenBudget = Field(default_factory=TokenBudget)
    items: list[ContextItem] = Field(default_factory=list)
    formatted_text: str = ""
    overflow: OverflowReport = Field(default_factory=OverflowReport)
    citation_context_attached: bool = False
