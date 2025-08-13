"""Configuration management for MCP Framework."""

from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global settings for MCP Framework."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Keys
    gemini_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for Google Gemini services."
    )
    openai_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for OpenAI services."
    )
    anthropic_api_key: str = Field(
        default="YOUR_API_KEY_HERE",
        description="API key for Anthropic Claude services.",
    )
    xai_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for xAI Grok services."
    )
    google_maps_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for Google Maps services."
    )

    # Google Calendar
    google_credentials_file: str = Field(
        default="~/.google_calendar_credentials.json",
        description="Path to Google Calendar OAuth2 credentials file.",
    )
    google_token_file: str = Field(
        default="~/.google_calendar_token.json",
        description="Path to Google Calendar OAuth2 token cache file.",
    )

    @property
    def google_credentials_path(self) -> Path:
        """Get resolved path for Google credentials."""
        return Path(self.google_credentials_file).expanduser()

    @property
    def google_token_path(self) -> Path:
        """Get resolved path for Google token."""
        return Path(self.google_token_file).expanduser()


settings = Settings()
