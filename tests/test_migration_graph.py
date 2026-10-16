from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_migrations_have_a_single_head():
    config = Config()
    config.set_main_option("script_location", "migrations")

    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20261016_merge_profile_heads"]
