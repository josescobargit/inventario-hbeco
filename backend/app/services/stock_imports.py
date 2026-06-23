from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

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
from app.schemas.stock_imports import (
    PhysicalCountDecision,
    PhysicalCountPreview,
    PhysicalCountPreviewRow,
    PhysicalCountRequestCreate,
    PhysicalCountRequestRead,
)


REQUEST_TYPE = "bulk_physical_count"


class PhysicalCountInvalidError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class PhysicalCountPendingError(Exception):
    pass


class PhysicalCountNotFoundError(Exception):
    pass


class PhysicalCountStatusError(Exception):
    pass


class PhysicalCountStaleError(Exception):
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus
        super().__init__(", ".join(skus))


def preview_physical_count(
    db: Session,
    filename: str,
    parsed_rows: list[dict[str, object]],
) -> PhysicalCountPreview:
    catalog_rows = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.is_active.is_(True))
        .order_by(Product.sku)
    ).all()
    stock_by_sku = {product.sku: (product, stock) for product, stock in catalog_rows}
    requested_skus = [str(row["sku"]) for row in parsed_rows]
    counts = Counter(requested_skus)
    duplicate_skus = sorted(sku for sku, count in counts.items() if count > 1)
    unknown_skus = sorted(set(requested_skus) - set(stock_by_sku))
    missing_skus = sorted(set(stock_by_sku) - set(requested_skus))

    preview_rows: list[PhysicalCountPreviewRow] = []
    for row in parsed_rows:
        sku = str(row["sku"])
        if sku not in stock_by_sku or sku in duplicate_skus:
            continue
        product, stock = stock_by_sku[sku]
        requested = int(row["physical_confirmed"])
        preview_rows.append(
            PhysicalCountPreviewRow(
                sku=sku,
                product_name=product.name,
                units_per_case=product.units_per_case,
                current_physical_confirmed=stock.physical_confirmed,
                requested_physical_confirmed=requested,
                difference=requested - stock.physical_confirmed,
            )
        )

    preview_rows.sort(key=lambda item: item.sku)
    valid = not missing_skus and not unknown_skus and not duplicate_skus
    return PhysicalCountPreview(
        filename=filename,
        valid=valid,
        catalog_products=len(stock_by_sku),
        file_products=len(parsed_rows),
        total_units=sum(row.requested_physical_confirmed for row in preview_rows),
        changed_products=sum(row.difference != 0 for row in preview_rows),
        missing_skus=missing_skus,
        unknown_skus=unknown_skus,
        duplicate_skus=duplicate_skus,
        rows=preview_rows,
    )


def request_physical_count(
    db: Session,
    request_data: PhysicalCountRequestCreate,
    actor_user_id: int,
) -> PhysicalCountRequestRead:
    normalized_lines = [
        {"sku": line.sku.upper().strip(), "requested_physical_confirmed": line.physical_confirmed}
        for line in request_data.lines
    ]
    skus = [line["sku"] for line in normalized_lines]
    duplicates = sorted(sku for sku, count in Counter(skus).items() if count > 1)
    if duplicates:
        raise PhysicalCountInvalidError(f"SKU duplicados: {', '.join(duplicates)}")

    catalog_rows = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.is_active.is_(True))
        .order_by(Product.sku)
        .with_for_update()
    ).all()
    stock_by_sku = {product.sku: (product, stock) for product, stock in catalog_rows}
    requested_set = set(skus)
    catalog_set = set(stock_by_sku)
    if requested_set != catalog_set:
        missing = sorted(catalog_set - requested_set)
        unknown = sorted(requested_set - catalog_set)
        details = []
        if missing:
            details.append(f"faltan: {', '.join(missing)}")
        if unknown:
            details.append(f"desconocidos: {', '.join(unknown)}")
        raise PhysicalCountInvalidError("Conteo incompleto; " + "; ".join(details))

    pending = db.scalar(
        select(Approval.id).where(
            Approval.request_type == REQUEST_TYPE,
            Approval.status == ApprovalStatus.solicitada.value,
        )
    )
    if pending is not None:
        raise PhysicalCountPendingError(str(pending))

    payload_lines = []
    for line in sorted(normalized_lines, key=lambda item: str(item["sku"])):
        product, stock = stock_by_sku[str(line["sku"])]
        payload_lines.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "current_physical_confirmed": stock.physical_confirmed,
                "requested_physical_confirmed": int(line["requested_physical_confirmed"]),
            }
        )

    approval = Approval(
        status=ApprovalStatus.solicitada.value,
        requested_by_user_id=actor_user_id,
        request_type=REQUEST_TYPE,
        reason=request_data.reason,
        payload_json=json.dumps({"version": 1, "lines": payload_lines}, ensure_ascii=True),
    )
    db.add(approval)
    db.flush()
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="request_bulk_physical_count",
            entity_type="approval",
            entity_id=approval.id,
            before_json=None,
            after_json=json.dumps(_summary(payload_lines), ensure_ascii=True),
            reason=request_data.reason,
        )
    )
    db.commit()
    db.refresh(approval)
    return _read_approval(approval)


def list_physical_count_requests(db: Session) -> list[PhysicalCountRequestRead]:
    approvals = db.scalars(
        select(Approval)
        .where(Approval.request_type == REQUEST_TYPE)
        .order_by(Approval.created_at.desc(), Approval.id.desc())
    ).all()
    return [_read_approval(approval) for approval in approvals]


def approve_physical_count(
    db: Session,
    approval_id: int,
    decision_data: PhysicalCountDecision,
    actor_user_id: int,
) -> PhysicalCountRequestRead:
    approval = _get_pending_approval(db, approval_id)
    payload_lines = _payload_lines(approval)
    product_ids = sorted(int(line["product_id"]) for line in payload_lines)
    rows = db.execute(
        select(Product, StockPosition)
        .join(StockPosition, StockPosition.product_id == Product.id)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
    ).all()
    stock_by_id = {product.id: (product, stock) for product, stock in rows}

    stale_skus = []
    for line in payload_lines:
        product_id = int(line["product_id"])
        if product_id not in stock_by_id:
            stale_skus.append(str(line["sku"]))
            continue
        _, stock = stock_by_id[product_id]
        if stock.physical_confirmed != int(line["current_physical_confirmed"]):
            stale_skus.append(str(line["sku"]))
    if stale_skus:
        raise PhysicalCountStaleError(sorted(stale_skus))

    for line in payload_lines:
        product, stock = stock_by_id[int(line["product_id"])]
        before = stock.physical_confirmed
        after = int(line["requested_physical_confirmed"])
        delta = after - before
        stock.physical_confirmed = after
        if delta == 0:
            continue
        db.add(
            StockMovement(
                product_id=product.id,
                user_id=actor_user_id,
                movement_type="CONTEO_FISICO_MASIVO",
                quantity=delta,
                reason=decision_data.reason,
                source_document_type="approval",
                source_document_id=approval.id,
                before_physical=before,
                after_physical=after,
            )
        )
        db.add(
            AuditLog(
                user_id=actor_user_id,
                action="apply_bulk_physical_count_line",
                entity_type="product",
                entity_id=product.id,
                before_json=json.dumps({"sku": product.sku, "physical_confirmed": before}),
                after_json=json.dumps({"sku": product.sku, "physical_confirmed": after}),
                reason=decision_data.reason,
            )
        )

    approval.status = ApprovalStatus.aplicada.value
    approval.approved_by_user_id = actor_user_id
    approval.decided_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="approve_bulk_physical_count",
            entity_type="approval",
            entity_id=approval.id,
            before_json=json.dumps({"status": ApprovalStatus.solicitada.value}),
            after_json=json.dumps({"status": ApprovalStatus.aplicada.value, **_summary(payload_lines)}),
            reason=decision_data.reason,
        )
    )
    db.commit()
    db.refresh(approval)
    return _read_approval(approval)


def reject_physical_count(
    db: Session,
    approval_id: int,
    decision_data: PhysicalCountDecision,
    actor_user_id: int,
) -> PhysicalCountRequestRead:
    approval = _get_pending_approval(db, approval_id)
    approval.status = ApprovalStatus.rechazada.value
    approval.approved_by_user_id = actor_user_id
    approval.decided_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            user_id=actor_user_id,
            action="reject_bulk_physical_count",
            entity_type="approval",
            entity_id=approval.id,
            before_json=json.dumps({"status": ApprovalStatus.solicitada.value}),
            after_json=json.dumps({"status": ApprovalStatus.rechazada.value}),
            reason=decision_data.reason,
        )
    )
    db.commit()
    db.refresh(approval)
    return _read_approval(approval)


def _get_pending_approval(db: Session, approval_id: int) -> Approval:
    approval = db.scalar(select(Approval).where(Approval.id == approval_id).with_for_update())
    if approval is None or approval.request_type != REQUEST_TYPE:
        raise PhysicalCountNotFoundError(str(approval_id))
    if approval.status != ApprovalStatus.solicitada.value:
        raise PhysicalCountStatusError(approval.status)
    return approval


def _payload_lines(approval: Approval) -> list[dict[str, object]]:
    payload = json.loads(approval.payload_json)
    return list(payload["lines"])


def _summary(lines: list[dict[str, object]]) -> dict[str, int]:
    return {
        "line_count": len(lines),
        "total_units": sum(int(line["requested_physical_confirmed"]) for line in lines),
        "changed_products": sum(
            int(line["requested_physical_confirmed"]) != int(line["current_physical_confirmed"])
            for line in lines
        ),
    }


def _read_approval(approval: Approval) -> PhysicalCountRequestRead:
    summary = _summary(_payload_lines(approval))
    return PhysicalCountRequestRead(
        approval_id=approval.id,
        status=approval.status,
        reason=approval.reason,
        created_at=approval.created_at,
        decided_at=approval.decided_at,
        **summary,
    )
