from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictConfigModel(BaseModel):
    """Configuration base that rejects misspelled or unexpected settings."""

    model_config = ConfigDict(extra="forbid")


class ProviderConfig(StrictConfigModel):
    name: Literal["openai_compatible", "openai", "azure_openai", "anthropic", "ollama"] = (
        "openai_compatible"
    )
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=256)
    api_key: Optional[str] = Field(default=None, max_length=8192)
    output_language: str = Field(default="English", min_length=1, max_length=64)
    # OpenAI-compatible options
    base_url: Optional[str] = Field(default=None, max_length=2048)
    organization: Optional[str] = Field(default=None, max_length=256)
    extra_headers: Dict[str, str] = Field(default_factory=dict)
    use_responses_api: bool = False
    # Azure OpenAI
    endpoint: Optional[str] = Field(default=None, max_length=2048)
    api_version: Optional[str] = Field(default="2024-02-15-preview", max_length=128)
    deployment: Optional[str] = Field(default=None, max_length=256)
    # Behavior
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=131_072)
    structured: bool = True
    json_mode_fallback: bool = True
    # Optional price for cost estimation ($ per 1k tokens).
    price_input_per_1k: Optional[float] = Field(default=None, ge=0.0)
    price_output_per_1k: Optional[float] = Field(default=None, ge=0.0)

    @field_validator("api_key", "base_url", "organization", "endpoint", "api_version", "deployment")
    @classmethod
    def reject_control_characters(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("control characters are not allowed")
        return value

    @field_validator("extra_headers")
    @classmethod
    def bound_extra_headers(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > 32:
            raise ValueError("at most 32 extra headers are allowed")
        for name, header_value in value.items():
            if not name or len(name) > 128 or len(header_value) > 8192:
                raise ValueError("extra header name or value is too long")
            if any(ord(char) < 32 or ord(char) == 127 for char in name + header_value):
                raise ValueError("control characters are not allowed in extra headers")
        return value


class RunConfig(StrictConfigModel):
    segmentation_strategy: Literal["dialog", "paragraph", "line"] = "dialog"
    max_segment_chars: int = Field(default=800, ge=100, le=100_000)
    concurrent_workers: int = Field(default=6, ge=1, le=32)
    rate_limit_rps: float = Field(default=2.0, ge=0.0, le=100.0)
    retry_max: int = Field(default=3, ge=0, le=5)
    timeout_sec: int = Field(default=60, ge=1, le=600)
    batch_size: int = Field(default=10, ge=1, le=100)
    # Soft ceiling for the assembled prompt (characters) to stay within model context.
    max_prompt_chars: int = Field(default=200_000, ge=100, le=2_000_000)
    stream_open_coding: bool = False
    stream_open_coding_threshold: int = Field(default=2000, ge=1, le=100_000)


class OutputConfig(StrictConfigModel):
    out_dir: str = Field(default="output", min_length=1, max_length=1024)
    save_graphviz: bool = True
    log_file: str = Field(default="analysis.log", min_length=1, max_length=1024)


class AppConfig(StrictConfigModel):
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
