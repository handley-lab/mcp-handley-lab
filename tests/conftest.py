import os
import pytest
import tempfile
from pathlib import Path

@pytest.fixture(scope="session")
def vcr_config():
    return {
        "record_mode": "once",
        "match_on": ["uri", "method"],
        "filter_headers": [
            "authorization",
            "x-api-key", 
            "x-goog-api-key",
            "cookie",
            "set-cookie",
        ],
        "filter_query_parameters": [
            "key",
            "access_token",
            "api_key",
        ],
        "filter_post_data_parameters": [
            "client_secret",
            "refresh_token",
            "access_token",
        ],
        "decode_compressed_response": True,
    }

@pytest.fixture
def temp_storage_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def test_output_file():
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)

@pytest.fixture
def test_json_file():
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        f.write('{"test": "data", "numbers": [1, 2, 3]}')
        f.flush()
        yield f.name
    Path(f.name).unlink(missing_ok=True)

@pytest.fixture
def skip_if_no_api_key():
    def _skip_if_no_key(env_var):
        if not os.getenv(env_var):
            pytest.skip(f"Skipping test - {env_var} not set")
    return _skip_if_no_key

@pytest.fixture(scope="session")
def google_calendar_test_config():
    """Configure Google Calendar to use test credentials during testing."""
    from mcp_handley_lab.common.config import settings
    
    # Check if test credentials exist
    test_creds_path = Path("~/.google_calendar_test_credentials.json").expanduser()
    test_token_path = Path("~/.google_calendar_test_token.json").expanduser()
    
    if not test_creds_path.exists():
        pytest.skip("Google Calendar test credentials not available")
    
    # Temporarily override settings for testing
    original_creds = settings.google_credentials_file
    original_token = settings.google_token_file
    
    settings.google_credentials_file = str(test_creds_path)
    settings.google_token_file = str(test_token_path)
    
    yield
    
    # Restore original settings
    settings.google_credentials_file = original_creds
    settings.google_token_file = original_token