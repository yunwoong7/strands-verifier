import os
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

class Config(BaseModel):
    aws_region: str = "us-west-2"
    aws_profile: Optional[str] = None
    model_id: str = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    max_tokens: int = 64000
    temperature: float = 0.1

    # Caching options
    enable_caching: bool = True
    cache_prompt: Optional[str] = "default"
    cache_tools: Optional[str] = "default"

    # Paths
    source_dir: str = "./source"
    target_dir: str = "./target"
    results_dir: str = "./results"
    traces_dir: str = "./traces"

    # OTEL & Arize
    arize_space_id: Optional[str] = None
    arize_api_key: Optional[str] = None
    arize_project_name: str = "strands-verifier"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            aws_region=os.getenv("AWS_REGION", "us-west-2"),
            aws_profile=os.getenv("AWS_PROFILE"),
            arize_space_id=os.getenv("ARIZE_SPACE_ID"),
            arize_api_key=os.getenv("ARIZE_API_KEY"),
        )