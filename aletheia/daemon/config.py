"""
Daemon Configuration
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class DaemonConfig:
    """Configuration for Aletheia Daemon."""
    
    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"
    
    # CORS settings
    cors_origins: list = None
    cors_allow_credentials: bool = True
    cors_allow_methods: list = None
    cors_allow_headers: list = None
    
    # Upload settings
    max_upload_size: int = 100 * 1024 * 1024  # 100MB
    upload_dir: str = "./uploads"
    
    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if self.cors_allow_methods is None:
            self.cors_allow_methods = ["*"]
        if self.cors_allow_headers is None:
            self.cors_allow_headers = ["*"]
    
    @classmethod
    def from_env(cls) -> "DaemonConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("ALETHEIA_HOST", "127.0.0.1"),
            port=int(os.getenv("ALETHEIA_PORT", "8000")),
            log_level=os.getenv("ALETHEIA_LOG_LEVEL", "info"),
            max_upload_size=int(os.getenv("ALETHEIA_MAX_UPLOAD_SIZE", str(100 * 1024 * 1024))),
            upload_dir=os.getenv("ALETHEIA_UPLOAD_DIR", "./uploads"),
        )
