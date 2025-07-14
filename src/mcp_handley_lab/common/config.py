"""Configuration management for MCP Framework."""
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings for MCP Framework."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Keys
    gemini_api_key: str = "YOUR_API_KEY_HERE"
    openai_api_key: str = "YOUR_API_KEY_HERE"
    anthropic_api_key: str = "YOUR_API_KEY_HERE"
    xai_api_key: str = "YOUR_API_KEY_HERE"
    google_maps_api_key: str = "YOUR_API_KEY_HERE"

    # Google Calendar
    google_credentials_file: str = "~/.google_calendar_credentials.json"
    google_token_file: str = "~/.google_calendar_token.json"

    @property
    def google_credentials_path(self) -> Path:
        """Get resolved path for Google credentials."""
        return Path(self.google_credentials_file).expanduser()

    @property
    def google_token_path(self) -> Path:
        """Get resolved path for Google token."""
        return Path(self.google_token_file).expanduser()


settings = Settings()
