from pathlib import Path

from career_pilot.database import ApplicationRepository
from career_pilot.models import ApplicationCreate


def test_application_crud(tmp_path: Path):
    repository = ApplicationRepository(tmp_path / "applications.db")
    created = repository.create(
        ApplicationCreate(company="示例公司", role="Agent 工程师", match_score=78)
    )
    assert created.id > 0
    assert repository.list()[0].company == "示例公司"

    updated = repository.update_status(created.id, "已投递", "官网投递")
    assert updated.status == "已投递"
    assert updated.notes == "官网投递"

    assert repository.delete(created.id) is True
    assert repository.list() == []

