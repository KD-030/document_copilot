from __future__ import annotations

from typing import Any

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "document-copilot"
    environment: str = "development"

    supabase_url: AnyHttpUrl = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: str = Field(..., min_length=1, alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(
        ..., min_length=1, alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    allowed_email_domains: str = Field(..., min_length=1, alias="ALLOWED_EMAIL_DOMAINS")

    database_url: str = Field(..., min_length=1, alias="DATABASE_URL")

    hf_token: str = Field(..., min_length=1, alias="HF_TOKEN")
    hf_chat_model: str = Field(
        default="meta-llama/Llama-3.1-8B-Instruct", alias="HF_CHAT_MODEL"
    )
    hf_embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5", alias="HF_EMBEDDING_MODEL"
    )
    hf_embedding_dimensions: int = Field(default=384, alias="HF_EMBEDDING_DIMENSIONS")

    allowed_origins: str = Field(
        default="http://localhost:5173", alias="ALLOWED_ORIGINS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def parsed_allowed_origins(self) -> list[str]:
        value = self.allowed_origins
        if value is None or value == "":
            return []
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @property
    def parsed_allowed_email_domains(self) -> set[str]:
        return {
            domain.strip().lower()
            for domain in self.allowed_email_domains.split(",")
            if domain.strip()
        }

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            return ",".join(
                str(origin).strip() for origin in value if str(origin).strip()
            )
        return str(value).strip()

    @field_validator("allowed_email_domains", mode="before")
    @classmethod
    def validate_allowed_email_domains(cls, value: Any) -> str:
        if isinstance(value, list):
            domains = [str(domain).strip().lower() for domain in value]
        else:
            domains = [domain.strip().lower() for domain in str(value or "").split(",")]
        if not domains or any(
            not domain or "@" in domain or "." not in domain for domain in domains
        ):
            raise ValueError(
                "ALLOWED_EMAIL_DOMAINS must be a comma-separated list of email domains"
            )
        return ",".join(domains)


settings = Settings()
