import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from src.config import Config
from src.utils import load_prompt, render_prompt
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class TargetLocator(BaseModel):
    page: int = Field(description="Line number or page reference")
    span: str = Field(description="Section or span identifier")

class ExtractedClaim(BaseModel):
    claim_id: str = Field(description="Unique identifier for the claim")
    claim_text: str = Field(description="The actual claim text")
    target_locator: TargetLocator = Field(description="Location information")
    category: str = Field(description="Category or section of the claim")

class ClaimsExtractionResult(BaseModel):
    """Complete claims extraction result."""
    claims: List[ExtractedClaim] = Field(description="List of extracted claims")

class ClaimExtractorAgent:
    def __init__(self, config: Config):
        self.config = config
        self.model = self._create_model()
        self.prompts = load_prompt("claim_extractor")

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
    def extract_claims(self, document_name: str, document_content: str) -> str:
        """
        Extract verifiable claims from a target document.

        Args:
            document_name: Name of the document being analyzed
            document_content: Full text content of the document

        Returns:
            JSON string containing extracted claims
        """
        try:
            agent = Agent(
                model=self.model,
                system_prompt=self.prompts["system_prompt"],
                trace_attributes={
                    "agent.type": "claim_extractor",
                    "document.name": document_name
                },
                name="ClaimExtractor"
            )

            user_prompt = render_prompt(
                self.prompts["user_prompt"],
                {
                    "document_name": document_name,
                    "document_content": document_content
                }
            )

            # Use structured_output for guaranteed JSON format
            result = agent.structured_output(ClaimsExtractionResult, user_prompt)

            return json.dumps(result.model_dump(), ensure_ascii=False)

        except Exception as e:
            return json.dumps({"error": f"Claim extraction failed: {str(e)}"})

def create_claim_extractor_tool(config: Config):
    """Factory function to create claim extractor tool"""
    extractor = ClaimExtractorAgent(config)
    return extractor.extract_claims