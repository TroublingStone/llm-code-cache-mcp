from pydantic import BaseModel, Field

from llm_code_cache.ingest.enums import NodeKind
from llm_code_cache.query.enums import UsageKind


class DefinitionResult(BaseModel):
    qualified_name: str
    name: str
    kind: NodeKind
    file_path: str
    start_line: int
    end_line: int
    source: str
    docstring: str | None = None
    parent_class: str | None = None
    decorators: list[str] = Field(default_factory=list)


class Usage(BaseModel):
    # Real nodes set qualified_name + kind; :Unresolved stubs set text_ref.
    # Invariant: (qualified_name is None) == (kind is None) == (text_ref is not None).
    qualified_name: str | None = None
    text_ref: str | None = None
    name: str
    kind: NodeKind | None = None
    usage_kind: UsageKind
    file_path: str
    start_line: int
    end_line: int


class SemanticHit(BaseModel):
    qualified_name: str
    score: float
    name: str
    kind: NodeKind
    file_path: str
    start_line: int
    end_line: int
    source: str
    # Augmented from graph; absent if augmentation skipped (e.g. graph miss).
    docstring: str | None = None
    parent_class: str | None = None
    decorators: list[str] = Field(default_factory=list)
