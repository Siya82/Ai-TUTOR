"""
RECOVERY NOTE: this file was NEVER read verbatim — only described in
docs/BUILD_LOG.md as "Pydantic settings loaded from .env". This is a
best-effort RECONSTRUCTION matching the documented env var names in
docs/LOCAL_SETUP.md (DATABASE_URL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
ENVIRONMENT, CORS_ORIGINS) and the field renames from
docs/ADR-010-deepseek-to-anthropic-migration.md
(deepseek_* -> anthropic_*). Treat as a working starting point, not
recovered code.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-6"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
