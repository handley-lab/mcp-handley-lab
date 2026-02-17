"""Configuration management for MCP Framework."""

import os
from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

# Restore API keys saved as _<KEY> by loop backends (_subscription_env).
# CLI auth is already locked in at startup; restoring here lets MCP servers use the keys.
_LLM_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")
for _key in _LLM_KEYS:
    if _key not in os.environ and f"_{_key}" in os.environ:
        os.environ[_key] = os.environ[f"_{_key}"]


class Settings(BaseSettings):
    """Global settings for MCP Framework."""

    model_config = ConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

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
    groq_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for Groq services."
    )
    xai_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for xAI Grok services."
    )
    mistral_api_key: str = Field(
        default="YOUR_API_KEY_HERE", description="API key for Mistral AI services."
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

    # Google Photos (reverse-engineered API, session-based auth)
    google_photos_session_file: str = Field(
        default="~/.local/share/gphotos/session.json",
        description="Path to Google Photos session file with cookies and WIZ tokens.",
    )

    # Otter.ai (undocumented API, session-based auth)
    otter_session_file: str = Field(
        default="~/.local/share/otter/session.json",
        description="Path to Otter.ai session file with cookies.",
    )
    otter_chrome_profile: str = Field(
        default="~/.local/share/otter/chrome-profile",
        description="Path to dedicated Chrome profile for Otter.ai Playwright refresh.",
    )
    otter_timeout: int = Field(
        default=30,
        description="HTTP timeout in seconds for Otter.ai API requests.",
    )

    @property
    def google_credentials_path(self) -> Path:
        """Get resolved path for Google credentials."""
        return Path(self.google_credentials_file).expanduser()

    @property
    def google_token_path(self) -> Path:
        """Get resolved path for Google token."""
        return Path(self.google_token_file).expanduser()

    @property
    def google_photos_session_path(self) -> Path:
        """Get resolved path for Google Photos session."""
        return Path(self.google_photos_session_file).expanduser()

    @property
    def otter_session_path(self) -> Path:
        """Get resolved path for Otter.ai session."""
        return Path(self.otter_session_file).expanduser()

    @property
    def otter_chrome_profile_path(self) -> Path:
        """Get resolved path for Otter.ai Chrome profile."""
        return Path(self.otter_chrome_profile).expanduser()


settings = Settings()
