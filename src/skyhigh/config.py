from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. No secrets in code."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str
    hold_duration_seconds: int = 120
    use_redis_seat_lock: bool = False
    seat_map_cache_ttl_seconds: int = 30
    idempotency_ttl_hours: int = 24
    seat_expiry_batch_size: int = 500
    seat_expiry_worker_interval_seconds: int = 15
    max_baggage_kg: float = 25.0
    log_level: str = "INFO"

    # Optional external weight verification (POST JSON {"passenger_id","declared_kg"} → {"verified_kg"}).
    weight_service_url: str | None = None
    weight_service_timeout_seconds: float = 3.0

    # Basic abuse protection (Redis fixed window; fail-open if Redis errors).
    rate_limit_enabled: bool = True
    rate_limit_get_per_minute: int = 240
    rate_limit_post_per_minute: int = 48

    # Per-passenger seat-hold burst (Redis fixed window; fail-open if Redis errors).
    passenger_hold_rate_limit_enabled: bool = True
    passenger_hold_rate_per_minute: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()
