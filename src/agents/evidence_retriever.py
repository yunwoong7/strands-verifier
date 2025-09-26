import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from src.config import Config
from src.utils import load_prompt, render_prompt
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class EvidenceLocation(BaseModel):
    page: int = Field(description="Page or line number")
    span: str = Field(description="Section or span identifier")

class Evidence(BaseModel):
    doc_id: str = Field(description="Source document identifier")
    evidence_text: str = Field(description="Relevant text from source")
    location: EvidenceLocation = Field(description="Location in source document")
    relevance_score: float = Field(description="Relevance score between 0-1")
    relationship: str = Field(description="supports|contradicts|relates")

class EvidenceRetrievalResult(BaseModel):
    """Complete evidence retrieval result."""
    evidence: List[Evidence] = Field(description="List of found evidence")

class EvidenceRetrieverAgent:
    def __init__(self, config: Config):
        self.config = config
        self.model = self._create_model()
        self.prompts = load_prompt("evidence_retriever")

    def _create_model(self) -> BedrockModel:
        session = boto3.Session(
            region_name=self.config.aws_region,
            profile_name=self.config.aws_profile
        )

        # Apply caching configuration if enabled
        model_kwargs = {
            "model_id": self.config.model_id,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "boto_session": session,
        }

        if self.config.enable_caching:
            if self.config.cache_prompt:
                model_kwargs["cache_prompt"] = self.config.cache_prompt
            if self.config.cache_tools:
                model_kwargs["cache_tools"] = self.config.cache_tools

        return BedrockModel(**model_kwargs)

    @tool
    def retrieve_evidence(self, claim_text: str, source_documents: str) -> str:
        """
        Search for evidence supporting or contradicting a claim in source documents.

        Args:
            claim_text: The claim to find evidence for
            source_documents: Text content of all source documents

        Returns:
            JSON string containing found evidence
        """
        try:
            agent = Agent(
                model=self.model,
                system_prompt=self.prompts["system_prompt"],
                trace_attributes={
                    "agent.type": "evidence_retriever",
                    "claim.text": claim_text[:100]  # First 100 chars for tracing
                },
                name="EvidenceRetriever"
            )

            user_prompt = render_prompt(
                self.prompts["user_prompt"],
                {
                    "claim_text": claim_text,
                    "source_documents": source_documents
                }
            )

            # Use messages with caching for source documents if caching is enabled
            if self.config.enable_caching and len(source_documents) > 1000:  # Only cache large documents
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"text": f"Source Documents:\n{source_documents}"},
                            {"cachePoint": {"type": "default"}},  # Cache the source documents
                            {"text": f"\nClaim to find evidence for: {claim_text}"}
                        ]
                    }
                ]
                agent_with_messages = Agent(
                    model=self.model,
                    system_prompt=self.prompts["system_prompt"],
                    messages=messages,
                    trace_attributes={
                        "agent.type": "evidence_retriever",
                        "claim.text": claim_text[:100],
                        "caching.enabled": True
                    },
                    name="EvidenceRetriever"
                )
                result = agent_with_messages.structured_output(
                    EvidenceRetrievalResult,
                    "Find evidence for the claim using the provided source documents."
                )
            else:
                # Standard processing without message caching
                result = agent.structured_output(EvidenceRetrievalResult, user_prompt)

            return json.dumps(result.model_dump(), ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": f"Evidence retrieval failed: {str(e)}"})

def create_evidence_retriever_tool(config: Config):
    """Factory function to create evidence retriever tool"""
    retriever = EvidenceRetrieverAgent(config)
    return retriever.retrieve_evidence