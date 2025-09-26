from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class TargetLocator(BaseModel):
    page: int
    span: str

class Citation(BaseModel):
    docId: str
    version: int
    page: int
    span: str
    note: Optional[str] = None

class ClaimDetails(BaseModel):
    claimText: str
    targetLocator: TargetLocator
    verdict: str
    confidence: int
    rationale: str
    citations: List[Citation]

class Claim(BaseModel):
    claim_id: str
    title: str
    description: str
    details: ClaimDetails
    priority: str
    dependencies: List[str]
    status: str

class BlockDetails(BaseModel):
    pageRange: List[int]

class Block(BaseModel):
    block_id: str
    title: str
    description: str
    details: BlockDetails
    priority: str
    status: str
    claims: List[Claim]

class SourceDocument(BaseModel):
    docId: str
    version: int
    kind: str

class Details(BaseModel):
    sourceDocuments: List[SourceDocument]

class Audit(BaseModel):
    createdBy: str
    createdAt: str
    reviewStage: str
    notes: str

class VerificationResult(BaseModel):
    document_id: str
    title: str
    description: str
    details: Details
    priority: str
    dependencies: List[str]
    status: str
    blocks: List[Block]
    audit: Audit