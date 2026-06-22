from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import (
    Approval,
    ApprovalStatus,
    AuditLog,
    Product,
    StockMovement,
    StockPosition,
)
from app.schemas.stock_adjustments import (
    StockAdjustmentDecision,
    StockAdjustmentRead,
    StockAdjustmentRequestCreate,
)


REQUEST_TYPE = "stock_adjustment"


class StockAdjustmentProductNotFoundError(Exception):
    pass


class StockAdjustmentApprovalNotFoundError(Exception):
    pass


class StockAdjustmentInvalidStatusError(Exception):
    pass


class StockAdjustmentInvalidTypeError(Exception):
    pass


def request_stock_adjustment(
    db: Session,
    adjustment_data: StockAdjustmentRequestCreate,
    actor_user_id: int,
) -> StockAdjustmentRead:
    sku = adjustment_data.sku.upper().strip()
    row = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.sku == sku)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise StockAdjustmentProductNotFoundError(sku)

    product, stock = row
    requested_physical = int(adjustment_data.requested_physical_confirmed)
    payload = {
        "sku": sku,
        "product_id": product.id,
        "current_physical_confirmed": stock.physical_confirmed,
        "requested_physical_confirmed": requested_physical,
    }

    approval = Approval(
        status=ApprovalStatus.solicitada.value,
        requested_by_user_id=actor_user_id,
        request_type=REQUEST_TYPE,
        reason=adjustment_data.reason,
        payload_json=json.dumps(payload, ensure_ascii=True),
    )
    db.add(approval)
    db.flush()

    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="request_stock_adjustment",
            entity_type="approval",
            entity_id=approval.id,
            before_json=json.dumps(
                {"sku": sku, "physical_confirmed": stock.physical_confirmed},
                ensure_ascii=True,
            ),
            after_json=json.dumps(
                {"sku": sku, "requested_physical_confirmed": requested_physical},
                ensure_ascii=True,
            ),
            reason=adjustment_data.reason,
        )
    )
    db.commit()
    db.refresh(approval)

    return _read_from_approval(approval)


def approve_stock_adjustment(
    db: Session,
    approval_id: int,
    decision_data: StockAdjustmentDecision,
    actor_user_id: int,
) -> StockAdjustmentRead:
    approval = _get_pending_stock_adjustment(db, approval_id)
    payload = _payload(approval)

    row = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.id == int(payload["product_id"]))
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise StockAdjustmentProductNotFoundError(str(payload["sku"]))

    product, stock = row
    before_physical = stock.physical_confirmed
    after_physical = int(payload["requested_physical_confirmed"])
    delta = after_physical - before_physical

    stock.physical_confirmed = after_physical
    approval.status = ApprovalStatus.aplicada.value
    approval.approved_by_user_id = actor_user_id
    approval.decided_at = datetime.now(timezone.utc)

    db.add(
        StockMovement(
            product_id=product.id,
            user_id=actor_user_id,
            movement_type="AJUSTE_STOCK_APROBADO",
            quantity=delta,
            reason=decision_data.reason,
            source_document_type="approval",
            source_document_id=approval.id,
            before_physical=before_physical,
            after_physical=after_physical,
        )
    )
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="approve_stock_adjustment",
            entity_type="approval",
            entity_id=approval.id,
            before_json=json.dumps(
                {"sku": product.sku, "physical_confirmed": before_physical},
                ensure_ascii=True,
            ),
            after_json=json.dumps(
                {"sku": product.sku, "physical_confirmed": after_physical},
                ensure_ascii=True,
            ),
            reason=decision_data.reason,
        )
    )
    db.commit()
    db.refresh(approval)

    return _read_from_approval(approval, current_physical_confirmed=after_physical)


def reject_stock_adjustment(
    db: Session,
    approval_id: int,
    decision_data: StockAdjustmentDecision,
    actor_user_id: int,
) -> StockAdjustmentRead:
    approval = _get_pending_stock_adjustment(db, approval_id)
    payload = _payload(approval)

    approval.status = ApprovalStatus.rechazada.value
    approval.approved_by_user_id = actor_user_id
    approval.decided_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="reject_stock_adjustment",
            entity_type="approval",
            entity_id=approval.id,
            before_json=json.dumps({"status": ApprovalStatus.solicitada.value}, ensure_ascii=True),
            after_json=json.dumps({"status": ApprovalStatus.rechazada.value}, ensure_ascii=True),
            reason=decision_data.reason,
        )
    )
    db.commit()
    db.refresh(approval)

    return _read_from_approval(
        approval,
        current_physical_confirmed=int(payload["current_physical_confirmed"]),
    )


def _get_pending_stock_adjustment(db: Session, approval_id: int) -> Approval:
    approval = db.scalar(
        select(Approval)
        .where(Approval.id == approval_id)
        .with_for_update()
    )
    if approval is None:
        raise StockAdjustmentApprovalNotFoundError(str(approval_id))
    if approval.request_type != REQUEST_TYPE:
        raise StockAdjustmentInvalidTypeError(str(approval_id))
    if approval.status != ApprovalStatus.solicitada.value:
        raise StockAdjustmentInvalidStatusError(str(approval_id))
    return approval


def _payload(approval: Approval) -> dict[str, object]:
    return json.loads(approval.payload_json)


def _read_from_approval(
    approval: Approval,
    current_physical_confirmed: Optional[int] = None,
) -> StockAdjustmentRead:
    payload = _payload(approval)
    current = (
        int(payload["current_physical_confirmed"])
        if current_physical_confirmed is None
        else current_physical_confirmed
    )
    return StockAdjustmentRead(
        approval_id=approval.id,
        sku=str(payload["sku"]),
        status=approval.status,
        current_physical_confirmed=current,
        requested_physical_confirmed=int(payload["requested_physical_confirmed"]),
        reason=approval.reason,
        created_at=approval.created_at,
        decided_at=approval.decided_at,
    )
