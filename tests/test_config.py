"""Unit tests for configuration management."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_framework.common.config import Settings, settings


class TestSettings:
    """Test cases for Settings class."""
    
    def test_default_values(self):
        """Test default configuration values."""
        # Clear environment variables for clean test
        env_vars_to_clear = ['GEMINI_API_KEY', 'OPENAI_API_KEY', 'GOOGLE_CREDENTIALS_FILE', 'GOOGLE_TOKEN_FILE']
        with patch.dict(os.environ, {}, clear=False):
            # Remove the variables we want to test defaults for
            for var in env_vars_to_clear:
                os.environ.pop(var, None)
            
            test_settings = Settings()
            
            assert test_settings.gemini_api_key == "YOUR_API_KEY_HERE"
            assert test_settings.openai_api_key == "YOUR_API_KEY_HERE"
            assert test_settings.google_credentials_file == "~/.google_calendar_credentials.json"
            assert test_settings.google_token_file == "~/.google_calendar_token.json"
    
    def test_environment_override(self):
        """Test that environment variables override defaults."""
        with patch.dict(os.environ, {
            'GEMINI_API_KEY': 'test_gemini_key',
            'OPENAI_API_KEY': 'test_openai_key',
            'GOOGLE_CREDENTIALS_FILE': '/custom/creds.json',
            'GOOGLE_TOKEN_FILE': '/custom/token.json'
        }):
            test_settings = Settings()
            
            assert test_settings.gemini_api_key == 'test_gemini_key'
            assert test_settings.openai_api_key == 'test_openai_key'
            assert test_settings.google_credentials_file == '/custom/creds.json'
            assert test_settings.google_token_file == '/custom/token.json'
    
    def test_google_credentials_path_property(self):
        """Test google_credentials_path property expands user path."""
        test_settings = Settings()
        test_settings.google_credentials_file = "~/test_credentials.json"
        
        result = test_settings.google_credentials_path
        
        assert isinstance(result, Path)
        assert str(result) == str(Path("~/test_credentials.json").expanduser())
        assert "~" not in str(result)  # Should be expanded
    
    def test_google_token_path_property(self):
        """Test google_token_path property expands user path."""
        test_settings = Settings()
        test_settings.google_token_file = "~/test_token.json"
        
        result = test_settings.google_token_path
        
        assert isinstance(result, Path)
        assert str(result) == str(Path("~/test_token.json").expanduser())
        assert "~" not in str(result)  # Should be expanded
    
    def test_absolute_paths_unchanged(self):
        """Test that absolute paths are not modified."""
        test_settings = Settings()
        test_settings.google_credentials_file = "/absolute/path/creds.json"
        test_settings.google_token_file = "/absolute/path/token.json"
        
        creds_path = test_settings.google_credentials_path
        token_path = test_settings.google_token_path
        
        assert str(creds_path) == "/absolute/path/creds.json"
        assert str(token_path) == "/absolute/path/token.json"


class TestGlobalSettings:
    """Test the global settings instance."""
    
    def test_settings_instance_exists(self):
        """Test that global settings instance is created."""
        assert settings is not None
        assert isinstance(settings, Settings)
    
    def test_settings_has_all_required_attributes(self):
        """Test that settings instance has all expected attributes."""
        assert hasattr(settings, 'gemini_api_key')
        assert hasattr(settings, 'openai_api_key')
        assert hasattr(settings, 'google_credentials_file')
        assert hasattr(settings, 'google_token_file')
        assert hasattr(settings, 'google_credentials_path')
        assert hasattr(settings, 'google_token_path')
    
    def test_settings_properties_work(self):
        """Test that property methods work on global instance."""
        # These should not raise exceptions
        creds_path = settings.google_credentials_path
        token_path = settings.google_token_path
        
        assert isinstance(creds_path, Path)
        assert isinstance(token_path, Path)


class TestConfigClass:
    """Test the Config inner class behavior."""
    
    def test_config_class_attributes(self):
        """Test Config class has expected attributes."""
        config = Settings.Config
        
        assert hasattr(config, 'env_file')
        assert hasattr(config, 'env_file_encoding')
        assert config.env_file == ".env"
        assert config.env_file_encoding == "utf-8"