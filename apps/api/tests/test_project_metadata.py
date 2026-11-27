from pathlib import Path
import tomllib


def test_migration_console_script_is_published_with_correct_name() -> None:
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    metadata = tomllib.loads(project_file.read_text(encoding="utf-8"))
    assert metadata["project"]["scripts"]["odei-migrate"] == "odei_api.migrate:main"
    assert "nodei-migrate" not in metadata["project"]["scripts"]
