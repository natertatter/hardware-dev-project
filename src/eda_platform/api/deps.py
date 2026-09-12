"""FastAPI dependencies."""

from fastapi import HTTPException

from eda_platform.api.project_loader import validate_project_id


def project_id_path(project_id: str) -> str:
    try:
        return validate_project_id(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid project_id") from None
