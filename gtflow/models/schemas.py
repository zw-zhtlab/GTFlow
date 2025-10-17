
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Segment(BaseModel):
    seg_id: str
    text: str
    speaker: Optional[str] = None
    meta: Dict[str, str] = Field(default_factory=dict)

class InitialCode(BaseModel):
    code: str
    definition: Optional[str] = None
    evidence_span: Optional[str] = None

class OpenCodingItem(BaseModel):
    seg_id: str
    in_vivo_phrases: List[str] = Field(default_factory=list)
    initial_codes: List[InitialCode] = Field(default_factory=list)
    quick_memo: Optional[str] = None

class CodebookEntry(BaseModel):
    code: str
    definition: str
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    positive_examples: List[str] = Field(default_factory=list)
    near_miss: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)

class Codebook(BaseModel):
    entries: List[CodebookEntry] = Field(default_factory=list)
    second_order_themes: Dict[str, List[str]] = Field(default_factory=dict)
    aggregate_dimensions: Dict[str, List[str]] = Field(default_factory=dict)

class AxialTriple(BaseModel):
    condition: str
    action: str
    result: str
    evidence: List[str] = Field(default_factory=list)

class Theory(BaseModel):
    core_category: str
    rationale: Optional[str] = None
    storyline: str
