
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal

class ProviderConfig(BaseModel):
    name: Literal["openai_compatible","openai","azure_openai","anthropic","ollama"] = "openai_compatible"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    # OpenAI-compatible options
    base_url: Optional[str] = None
    organization: Optional[str] = None
    extra_headers: Dict[str, str] = Field(default_factory=dict)
    use_responses_api: bool = False
    # Azure OpenAI
    endpoint: Optional[str] = None
    api_version: Optional[str] = "2024-02-15-preview"
    deployment: Optional[str] = None
    # Behavior
    temperature: float = 0.2
    max_tokens: int = 1024
    structured: bool = True
    json_mode_fallback: bool = True
    # price for estimation ($ per 1k tokens)
    price_input_per_1k: float = 0.002
    price_output_per_1k: float = 0.006

class RunConfig(BaseModel):
    segmentation_strategy: Literal["dialog","paragraph","line"] = "dialog"
    max_segment_chars: int = 800
    concurrent_workers: int = 6
    rate_limit_rps: float = 2.0
    retry_max: int = 3
    timeout_sec: int = 60
    batch_size: int = 10

class OutputConfig(BaseModel):
    out_dir: str = "output"
    save_graphviz: bool = True
    log_file: str = "analysis.log"

class AppConfig(BaseModel):
    provider: ProviderConfig = ProviderConfig()
    run: RunConfig = RunConfig()
    output: OutputConfig = OutputConfig()
