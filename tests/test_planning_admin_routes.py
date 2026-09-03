def test_planning_module_imports_abort():
    from app.routes import planning

    assert hasattr(planning, "abort")
