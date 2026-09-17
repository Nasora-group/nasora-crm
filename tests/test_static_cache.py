def test_static_asset_cache_policy(app):
    assert app.config["SEND_FILE_MAX_AGE_DEFAULT"] == 86400
