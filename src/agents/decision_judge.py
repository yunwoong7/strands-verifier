import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from src.config import Config
from src.utils import load_prompt, render_prompt
import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field

class DecisionJudgmentResult(BaseModel):
    """Complete decision judgment result."""
    verdict: str = Field(description="Must be one of: SUPPORTED, CONTRADICTED, PARTIAL, NOT_FOUND")
    confidence: int = Field(description="Confidence score from 0-100", ge=0, le=100)
    rationale: str = Field(description="Detailed explanation of the decision - REQUIRED field")
    supporting_evidence: List[str] = Field(default_factory=list, description="IDs of supporting evidence")
    contradicting_evidence: List[str] = Field(default_factory=list, description="IDs of contradicting evidence")

class DecisionJudgeAgent:
    def __init__(self, config: Config):
        self.config = config
        self.model = self._create_model()
        self.prompts = load_prompt("decision_judge")

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
    def judge_claim(self, claim_text: str, evidence_data: str) -> str:
        """
        Evaluate a claim against evidence and make a verification decision.

        Args:
            claim_text: The claim to evaluate
            evidence_data: JSON string containing evidence data

        Returns:
            JSON string containing verdict, confidence, and rationale
        """
        try:
            agent = Agent(
                model=self.model,
                system_prompt=self.prompts["system_prompt"],
                name="DecisionJudge",
                trace_attributes={
                    "agent.type": "decision_judge"
                }
            )

            user_prompt = render_prompt(
                self.prompts["user_prompt"],
                {
                    "claim_text": claim_text,
                    "evidence_data": evidence_data
                }
            )

            # Try structured_output first, fallback to regular text parsing
            try:
                result = agent.structured_output(DecisionJudgmentResult, user_prompt)
                return json.dumps(result.model_dump(), ensure_ascii=False)
            except Exception as e:
                # Fallback to text-based response parsing
                response = agent(user_prompt + "\n\nProvide your response in JSON format with verdict, confidence, and rationale fields.")
                response_text = str(response)

                # Try to extract structured information from text response
                try:
                    # Look for JSON in the response
                    import re
                    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                    if json_match:
                        return json_match.group(0)
                    else:
                        # Create minimal valid response
                        return json.dumps({
                            "verdict": "NOT_FOUND",
                            "confidence": 0,
                            "rationale": f"Failed to parse structured output: {response_text[:200]}",
                            "supporting_evidence": [],
                            "contradicting_evidence": []
                        })
                except:
                    return json.dumps({
                        "verdict": "NOT_FOUND",
                        "confidence": 0,
                        "rationale": f"Complete parsing failure: {str(e)}",
                        "supporting_evidence": [],
                        "contradicting_evidence": []
                    })

        except Exception as e:
            return json.dumps({"error": f"Decision judgment failed: {str(e)}"})

def create_decision_judge_tool(config: Config):
    """Factory function to create decision judge tool"""
    judge = DecisionJudgeAgent(config)
    return judge.judge_claim