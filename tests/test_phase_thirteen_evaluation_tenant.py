from app.models import Evaluation


def test_evaluation_declares_required_nasora_tenant_id():
    column = Evaluation.__table__.columns["tenant_id"]

    assert column.nullable is False
    assert column.default is not None
    assert column.default.arg == 116
    assert column.index is True


def test_evaluation_tenant_id_can_be_overridden_explicitly():
    evaluation = Evaluation(
        tenant_id=123,
        commercial_id=1,
        year=2026,
        month=10,
    )

    assert evaluation.tenant_id == 123
