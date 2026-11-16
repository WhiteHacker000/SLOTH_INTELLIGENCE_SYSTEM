from fastapi import APIRouter
from pydantic import BaseModel

from app.api.security import AdminKeyHeader, SettingsDep, admin_key_valid

router = APIRouter(tags=["admin"])


class AdminStatus(BaseModel):
    key_required: bool
    key_valid: bool


@router.get("/admin", response_model=AdminStatus)
def admin_status(
    settings: SettingsDep, x_admin_key: AdminKeyHeader = None
) -> AdminStatus:
    """Tells the UI whether import and extraction need a key, and if this one works."""
    return AdminStatus(
        key_required=settings.admin_api_key is not None,
        key_valid=admin_key_valid(settings, x_admin_key),
    )
