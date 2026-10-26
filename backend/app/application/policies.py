from dataclasses import dataclass


@dataclass(frozen=True)
class Policies:
    login_max_attempts: int = 10
    login_block_seconds: int = 900

    bulk_delay_min: float = 3.0
    bulk_delay_max: float = 8.0
    bulk_concurrency: int = 3
    flood_wait_max: int = 120

    stats_refresh_minutes: int = 30
    stats_refresh_days: int = 7

    messages_sync_minutes: int = 0
    messages_sync_dialogs: int = 50

    media_max_size: int = 2**30
    media_concurrency: int = 2
    media_link_ttl: int = 3600

    login_flow_ttl: int = 900
    dialogs_cache_ttl: int = 60
