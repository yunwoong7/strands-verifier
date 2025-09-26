import yaml
import json
from typing import Dict, Any
from pathlib import Path

def load_prompt(prompt_name: str) -> Dict[str, str]:
    """Load prompt template from YAML file"""
    prompt_path = Path(f"src/prompts/{prompt_name}.yaml")
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def render_prompt(template: str, variables: Dict[str, Any]) -> str:
    """Render prompt template with variables using simple {{}} replacement"""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result

def load_txt_file(file_path: str) -> str:
    """Load TXT file content with UTF-8 encoding"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def save_json_result(data: Dict[str, Any], file_path: str) -> None:
    """Save result data as JSON file"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)