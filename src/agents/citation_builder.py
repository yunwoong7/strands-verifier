import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from src.config import Config
from src.utils import load_prompt, render_prompt
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class Citation(BaseModel):
    docId: str = Field(description="Source document ID")
    version: int = Field(description="Document version number")
    page: int = Field(description="Page or line number")
    span: str = Field(description="Section or span identifier")
    note: Optional[str] = Field(default=None, description="Additional context or explanation")

class CitationBuildingResult(BaseModel):
    """Complete citation building result."""
    citations: List[Citation] = Field(description="List of formatted citations")

class CitationBuilderAgent:
    def __init__(self, config: Config):
        self.config = config
        self.model = self._create_model()
        self.prompts = load_prompt("citation_builder")

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
    def build_citations(self, evidence_data: str, source_metadata: str) -> str:
        """
        Create proper citations from evidence sources.

        Args:
            evidence_data: JSON string containing evidence information
            source_metadata: JSON string containing source document metadata

        Returns:
            JSON string containing formatted citations
        """
        try:
            agent = Agent(
                model=self.model,
                system_prompt=self.prompts["system_prompt"],
                trace_attributes={
                    "agent.type": "citation_builder"
                },
                name="CitationBuilder"
            )

            user_prompt = render_prompt(
                self.prompts["user_prompt"],
                {
                    "evidence_data": evidence_data,
                    "source_metadata": source_metadata
                }
            )

            # Use structured_output for guaranteed JSON format
            result = agent.structured_output(CitationBuildingResult, user_prompt)

            return json.dumps(result.model_dump(), ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": f"Citation building failed: {str(e)}"})

def create_citation_builder_tool(config: Config):
    """Factory function to create citation builder tool"""
    builder = CitationBuilderAgent(config)
    return builder.build_citations