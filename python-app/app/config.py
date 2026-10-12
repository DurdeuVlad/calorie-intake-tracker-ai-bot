"""Runtime configuration. Mirrors BotProperties/MessagingProperties/application.yml exactly
(same env var names) so Coolify deployment config carries over unchanged."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramFrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore", populate_by_name=True)

    telegram_frontend_enabled: bool = Field(default=True, alias="TELEGRAM_FRONTEND_ENABLED")
    allowed_telegram_user_ids: str = Field(default="", alias="ALLOWED_TELEGRAM_USER_IDS")
    # Bootstrap-only administrator IDs. Runtime access is stored in Postgres;
    # this value is used to seed/reassert administrators during deployment.
    admin_telegram_user_ids: str = Field(default="", alias="ADMIN_TELEGRAM_USER_IDS")

    @property
    def allowed_user_ids(self) -> set[str]:
        return {v.strip() for v in self.allowed_telegram_user_ids.split(",") if v.strip()}


class MattermostFrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore", populate_by_name=True)

    mattermost_frontend_enabled: bool = Field(default=False, alias="MATTERMOST_FRONTEND_ENABLED")
    mattermost_internal_url: str = Field(default="", alias="MATTERMOST_INTERNAL_URL")
    mattermost_bot_token: str = Field(default="", alias="MATTERMOST_BOT_TOKEN")
    mattermost_bot_user_id: str = Field(default="", alias="MATTERMOST_BOT_USER_ID")
    allowed_mattermost_user_ids: str = Field(default="", alias="ALLOWED_MATTERMOST_USER_IDS")

    @property
    def allowed_user_ids(self) -> set[str]:
        return {v.strip() for v in self.allowed_mattermost_user_ids.split(",") if v.strip()}

    @property
    def enabled(self) -> bool:
        return bool(
            self.mattermost_frontend_enabled
            and self.mattermost_internal_url
            and self.mattermost_bot_token
            and self.mattermost_bot_user_id
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False, populate_by_name=True)

    # Database (JDBC-style URL kept for env-var compatibility; converted to an asyncpg DSN in db/base.py)
    database_url: str = Field(default="jdbc:postgresql://localhost:5432/foodjournal", alias="DATABASE_URL")
    database_username: str = Field(default="foodjournal", alias="DATABASE_USERNAME")
    database_password: str = Field(default="foodjournal", alias="DATABASE_PASSWORD")

    # Telegram / core bot
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    allowed_telegram_user_ids: str = Field(default="", alias="ALLOWED_TELEGRAM_USER_IDS")
    admin_telegram_user_ids: str = Field(default="", alias="ADMIN_TELEGRAM_USER_IDS")
    default_timezone: str = Field(default="Europe/Bucharest", alias="DEFAULT_TIMEZONE")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.6-luna", alias="OPENAI_MODEL")
    agent_max_tool_calls: int = Field(default=10, alias="AGENT_MAX_TOOL_CALLS")
    openai_transcription_model: str = Field(default="gpt-4o-mini-transcribe", alias="OPENAI_TRANSCRIPTION_MODEL")

    # Mobile API auth. MOBILE_AUTH_JWT_SECRET signs access tokens; when empty the
    # app falls back to a per-process ephemeral secret (dev only -- tokens die on
    # restart). Production deployments must set it.
    mobile_auth_jwt_secret: str = Field(default="", alias="MOBILE_AUTH_JWT_SECRET")
    mobile_auth_access_token_ttl_minutes: int = Field(default=30, alias="MOBILE_AUTH_ACCESS_TOKEN_TTL_MINUTES")
    mobile_auth_refresh_token_ttl_days: int = Field(default=30, alias="MOBILE_AUTH_REFRESH_TOKEN_TTL_DAYS")
    mobile_auth_rate_limit_per_minute: int = Field(default=10, alias="MOBILE_AUTH_RATE_LIMIT_PER_MINUTE")
    mobile_message_rate_limit_per_minute: int = Field(default=60, alias="MOBILE_MESSAGE_RATE_LIMIT_PER_MINUTE")

    # Nutrition / web tools
    open_food_facts_base_url: str = Field(
        default="https://world.openfoodfacts.org/api/v2", alias="OPEN_FOOD_FACTS_BASE_URL"
    )
    searxng_base_url: str = Field(default="", alias="SEARXNG_BASE_URL")
    browserless_base_url: str = Field(default="", alias="BROWSERLESS_BASE_URL")
    browserless_token: str = Field(default="", alias="BROWSERLESS_TOKEN")

    # Messaging frontends
    telegram_frontend_enabled: bool = Field(default=True, alias="TELEGRAM_FRONTEND_ENABLED")
    mattermost_frontend_enabled: bool = Field(default=False, alias="MATTERMOST_FRONTEND_ENABLED")
    mattermost_internal_url: str = Field(default="", alias="MATTERMOST_INTERNAL_URL")
    mattermost_bot_token: str = Field(default="", alias="MATTERMOST_BOT_TOKEN")
    mattermost_bot_user_id: str = Field(default="", alias="MATTERMOST_BOT_USER_ID")
    allowed_mattermost_user_ids: str = Field(default="", alias="ALLOWED_MATTERMOST_USER_IDS")

    # Scheduling / polling
    management_port: int = Field(default=8081, alias="MANAGEMENT_PORT")
    food_journal_scheduling_enabled: bool = Field(default=True, alias="FOOD_JOURNAL_SCHEDULING_ENABLED")
    food_journal_outbox_delay_ms: int = Field(default=5000, alias="FOOD_JOURNAL_OUTBOX_DELAY_MS")
    food_journal_inbox_delay_ms: int = Field(default=500, alias="FOOD_JOURNAL_INBOX_DELAY_MS")

    @field_validator("agent_max_tool_calls")
    @classmethod
    def _clamp_agent_max_tool_calls(cls, value: int) -> int:
        # Java clamps to min(value, 10) with a <=0 -> 10 default. We clamp both ends for robustness.
        if value <= 0:
            return 10
        return max(1, min(10, value))

    @field_validator("mobile_auth_access_token_ttl_minutes")
    @classmethod
    def _clamp_access_token_ttl(cls, value: int) -> int:
        # Mobile access tokens are deliberately short-lived (audit: 15-60 min).
        if value <= 0:
            return 30
        return max(15, min(60, value))

    @field_validator("mobile_auth_refresh_token_ttl_days")
    @classmethod
    def _default_refresh_ttl(cls, value: int) -> int:
        return value if value > 0 else 30

    @field_validator("mobile_auth_rate_limit_per_minute")
    @classmethod
    def _default_auth_rate_limit(cls, value: int) -> int:
        return value if value > 0 else 10

    @field_validator("mobile_message_rate_limit_per_minute")
    @classmethod
    def _default_message_rate_limit(cls, value: int) -> int:
        return value if value > 0 else 60

    @property
    def allowed_telegram_user_id_set(self) -> set[str]:
        return {v.strip() for v in self.allowed_telegram_user_ids.split(",") if v.strip()}

    @property
    def admin_telegram_user_id_set(self) -> set[str]:
        return {v.strip() for v in self.admin_telegram_user_ids.split(",") if v.strip()}

    @property
    def allowed_mattermost_user_id_set(self) -> set[str]:
        return {v.strip() for v in self.allowed_mattermost_user_ids.split(",") if v.strip()}

    @property
    def mattermost_enabled(self) -> bool:
        return bool(
            self.mattermost_frontend_enabled
            and self.mattermost_internal_url
            and self.mattermost_bot_token
            and self.mattermost_bot_user_id
        )

    @property
    def asyncpg_dsn(self) -> str:
        """Convert the JDBC-style DATABASE_URL (jdbc:postgresql://host:port/db) into an asyncpg DSN."""
        url = self.database_url
        if url.startswith("jdbc:"):
            url = url[len("jdbc:") :]
        # url is now postgresql://host:port/db[?params]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        host_part = url.split("://", 1)[1]
        # Windows resolves "localhost" to ::1 first, and Docker Desktop's IPv6
        # port proxy accepts the TCP connection but stalls the Postgres
        # handshake (connects hang until timeout). Pin the loopback name to
        # IPv4 so local dev/test connects reliably; real hostnames are untouched.
        if host_part == "localhost" or host_part.startswith(("localhost:", "localhost/")):
            host_part = "127.0.0.1" + host_part[len("localhost") :]
        return f"postgresql+asyncpg://{self.database_username}:{self.database_password}@{host_part}"


class TerminalSettings(BaseSettings):
    """Mirrors TerminalProperties.java (food-journal.terminal.*), used only by the
    terminal REPL / eval harness entrypoint, never by the production server."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False, populate_by_name=True)

    runner_enabled: bool = Field(default=True, alias="TERMINAL_RUNNER_ENABLED")
    user_id: int = Field(default=1, alias="TERMINAL_TELEGRAM_USER_ID")
    display_name: str = Field(default="Local developer", alias="TERMINAL_DISPLAY_NAME")
    eval_file: str = Field(default="", alias="TERMINAL_EVAL_FILE")
    report_file: str = Field(default="", alias="TERMINAL_EVAL_REPORT_FILE")
    eval_repeats: int = Field(default=3, alias="TERMINAL_EVAL_REPEATS")
    eval_scenario: str = Field(default="", alias="TERMINAL_EVAL_SCENARIO")
    eval_baseline_file: str = Field(default="", alias="TERMINAL_EVAL_BASELINE_FILE")
    eval_full_report: bool = Field(default=True, alias="TERMINAL_EVAL_FULL_REPORT")

    @field_validator("user_id")
    @classmethod
    def _default_user_id(cls, value: int) -> int:
        return value if value > 0 else 1

    @field_validator("display_name")
    @classmethod
    def _default_display_name(cls, value: str) -> str:
        return value.strip() or "Local developer"

    @field_validator("eval_repeats")
    @classmethod
    def _default_eval_repeats(cls, value: int) -> int:
        return value if value > 0 else 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_terminal_settings() -> TerminalSettings:
    return TerminalSettings()
