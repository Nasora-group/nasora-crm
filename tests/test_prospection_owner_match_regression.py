from app.routes.dashboard import _find_client_for_prospection


def test_owner_scoped_helper_is_present():
    assert callable(_find_client_for_prospection)
