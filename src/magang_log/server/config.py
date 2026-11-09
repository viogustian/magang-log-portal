"""Server configuration and loopback host enforcement."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass


def is_loopback(host: str) -> bool:
    """Return True if host is localhost or a valid loopback IP address."""
    clean_host = host.strip().lower()
    if clean_host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(clean_host)
        return ip.is_loopback
    except ValueError:
        return False


@dataclass
class ServerConfig:
    """Configuration for local FastAPI/Uvicorn server with strict loopback binding."""

    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    log_level: str = "info"

    def __post_init__(self) -> None:
        if not is_loopback(self.host):
            raise ValueError(
                f"Invalid host '{self.host}'. Server must bind strictly to a loopback interface "
                "(e.g., 127.0.0.1, localhost). External network binding is strictly prohibited."
            )

