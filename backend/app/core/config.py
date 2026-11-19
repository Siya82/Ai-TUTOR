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
    # NEW 19 Nov 2026 (ADR-035, AI cost). Model for marking assignment
    # answers -- a short, structured judgement that a smaller, cheaper model
    # does well. Empty = use anthropic_model (unchanged behaviour). Set
    # MARKING_MODEL in backend/.env to a Haiku-class model to cut marking
    # cost, e.g. MARKING_MODEL=claude-haiku-5-5.
    marking_model: str = ""
    # NEW 19 Nov 2026 (ADR-043). How parent sign-up codes are sent; see
    # app/services/sms.py. Empty = off (in development: written to the log).
    sms_provider: str = ""
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:5173"]

    # NEW 13 Nov 2026 (ADR-016, student file attachments). Relative to the
    # working directory uvicorn is started from (backend/, per
    # docs/LOCAL_SETUP.md) unless overridden. Git-ignored -- runtime data,
    # not source.
    upload_dir: str = "uploads/attachments"

    # NEW 14 Nov 2026 (ADR-017, student login). No default on purpose --
    # the app refuses to start without a real secret, same posture as
    # anthropic_api_key above. Add JWT_SECRET_KEY to backend/.env; a
    # strong random value can be generated with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # NEW 14 Nov 2026 (ADR-021, RAG content ingestion/retrieval). Unlike
    # anthropic_api_key/jwt_secret_key above, this one DOES default to
    # None rather than being required -- the app must keep starting and
    # serving every existing tutor turn with no change in behaviour for
    # everyone who hasn't set it. Only app/services/embeddings.py reads
    # this, and only once scripts/ingest_content.py has actually written
    # real (non-placeholder) ContentChunk rows for a topic -- see
    # app/services/retrieval.py's short-circuit. Add OPENAI_API_KEY to
    # backend/.env yourself to use it; same standing rule as every other
    # secret in this file, Claude never reads or writes .env contents.
    openai_api_key: str | None = None


settings = Settings()
