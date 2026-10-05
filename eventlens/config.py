import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "ProsusAI/finbert"
MODEL_REVISION = "4556d13015211d73dccd3fdd39d39232506f3e43"
MODEL_SHA256 = "e15a7b5738df7f17553399b6d94c6e2ff69c89245d066e8e5d183f5803a554e3"
ENGINE_VERSION = "rules2-finbert1"


@dataclass(frozen=True)
class Settings:
    database_path: Path = ROOT / "runtime" / "eventlens.sqlite3"
    model_cache: Path = ROOT / ".cache" / "huggingface" / "hub"
    replay_directory: Path = ROOT / "data"
    asset_directory: Path = ROOT / "data"
    frontend_directory: Path = ROOT / "frontend" / "dist"
    source_limit: int = 5
    refresh_interval_seconds: int = 300
    live_max_age_hours: int = 72
    write_token: str = ""
    public_mode: bool = False
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")

    def __post_init__(self):
        if not 1 <= self.source_limit <= 20:
            raise ValueError("source_limit must be between 1 and 20")
        if self.public_mode and len(self.write_token) < 24:
            raise ValueError("Public mode requires EVENTLENS_WRITE_TOKEN of at least 24 characters")
        if not self.allowed_hosts or "*" in self.allowed_hosts:
            raise ValueError("Explicit allowed hosts are required; wildcards are not supported")

    @classmethod
    def from_environment(cls):
        return cls(
            database_path=Path(
                os.getenv("EVENTLENS_DATABASE", str(ROOT / "runtime" / "eventlens.sqlite3"))
            ),
            write_token=os.getenv("EVENTLENS_WRITE_TOKEN", ""),
            public_mode=os.getenv("EVENTLENS_PUBLIC", "false").lower() == "true",
            allowed_hosts=tuple(
                host.strip()
                for host in os.getenv("EVENTLENS_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
                if host.strip()
            ),
        )
