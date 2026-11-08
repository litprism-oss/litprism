from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    database_url: str = "sqlite+aiosqlite:///./litprism.db"
    llm_provider: str = "openai"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = "gpt-5.4-mini"
    azure_api_key: str = ""
    azure_api_base: str = ""
    azure_api_version: str = "2024-02-01"
    azure_deployment_name: str = ""
    ollama_base_url: str = "http://localhost:11434"
    pubmed_api_key: str = ""
    semantic_scholar_api_key: str = ""
    upload_dir: str = "~/.litprism/uploads"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    debug: bool = False
    secret_key: str = ""
    unpaywall_email: str = ""
    # Comma-separated list of allowed browser origins, e.g.
    # "https://litprism.vercel.app,https://litprism.org". "*" allows any origin.
    cors_origins: str = "*"
    # Auth (Supabase). SUPABASE_URL is the project URL, used for the JWKS endpoint and issuer.
    supabase_url: str = ""
    # Only for legacy HS256 Supabase projects; leave empty to verify via JWKS.
    supabase_jwt_secret: str = ""
    # Local dev / tests: every request is the fixed dev user, no token needed.
    auth_disabled: bool = False
    # Comma-separated emails with unlimited credits (Session 16.3).
    admin_emails: str = ""
    # First non-anonymous login with this email claims all ownerless projects.
    bootstrap_owner_email: str = ""

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """Hosted Postgres (Supabase, Fly, Neon) hands out plain postgres:// URLs."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix) :]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]


settings = Settings()
