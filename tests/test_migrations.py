import ast
from pathlib import Path


ALEMBIC_VERSION_LIMIT = 32


def _string_assignment(module_path: Path, name: str) -> str | None:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != name:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


def test_alembic_revision_ids_fit_postgres_version_table() -> None:
    """Human meaning: Alembic stores the current migration id in a 32-char column, so ids must stay short."""

    migration_paths = sorted(Path("alembic/versions").glob("*.py"))

    too_long = []
    for migration_path in migration_paths:
        for field_name in ("revision", "down_revision"):
            value = _string_assignment(migration_path, field_name)
            if value is not None and len(value) > ALEMBIC_VERSION_LIMIT:
                too_long.append(f"{migration_path.name}:{field_name}={value}")

    assert too_long == []
