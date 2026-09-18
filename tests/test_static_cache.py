from app import create_app
from app.config import TestingConfig


def test_static_asset_cache_policy():
    app = create_app(TestingConfig)
    assert app.config["SEND_FILE_MAX_AGE_DEFAULT"] == 86400
