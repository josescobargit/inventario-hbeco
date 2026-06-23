from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.inventory import User
from app.schemas.incidents import IncidentRead
from app.services.tracking import list_incident_summaries


router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
def read_incidents(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(Permission.view_inventory)),
) -> list[IncidentRead]:
    return list_incident_summaries(db, limit)
