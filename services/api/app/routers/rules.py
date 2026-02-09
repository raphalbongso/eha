"""CRUD routes for email matching rules."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_id, get_db
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleResponse, RuleUpdate
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """List all rules for the current user."""
    result = await db.execute(
        select(Rule)
        .where(Rule.user_id == user_id)
        .order_by(Rule.created_at.desc())
    )
    rules = result.scalars().all()
    return [
        RuleResponse(
            id=str(r.id),
            name=r.name,
            conditions=r.conditions,
            is_active=r.is_active,
            created_at=r.created_at.isoformat(),
            updated_at=r.updated_at.isoformat(),
        )
        for r in rules
    ]


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new email matching rule."""
    rule = Rule(
        user_id=user_id,
        name=body.name,
        conditions=body.conditions.model_dump(),
        is_active=body.is_active,
    )
    db.add(rule)
    await db.flush()

    await write_audit_log(
        db=db,
        user_id=user_id,
        action="rule.created",
        entity_type="rule",
        entity_id=str(rule.id),
        metadata={"name": rule.name},
    )

    return RuleResponse(
        id=str(rule.id),
        name=rule.name,
        conditions=rule.conditions,
        is_active=rule.is_active,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
    )


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific rule."""
    result = await db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return RuleResponse(
        id=str(rule.id),
        name=rule.name,
        conditions=rule.conditions,
        is_active=rule.is_active,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
    )


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a rule."""
    result = await db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if body.name is not None:
        rule.name = body.name
    if body.conditions is not None:
        rule.conditions = body.conditions.model_dump()
    if body.is_active is not None:
        rule.is_active = body.is_active

    await db.flush()

    await write_audit_log(
        db=db,
        user_id=user_id,
        action="rule.updated",
        entity_type="rule",
        entity_id=str(rule.id),
    )

    return RuleResponse(
        id=str(rule.id),
        name=rule.name,
        conditions=rule.conditions,
        is_active=rule.is_active,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat(),
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a rule."""
    result = await db.execute(
        select(Rule).where(Rule.id == rule_id, Rule.user_id == user_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await write_audit_log(
        db=db,
        user_id=user_id,
        action="rule.deleted",
        entity_type="rule",
        entity_id=str(rule.id),
        metadata={"name": rule.name},
    )

    await db.delete(rule)
