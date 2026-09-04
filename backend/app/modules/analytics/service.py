from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import select

from ...extensions import db
from ..auth.models import User
from ..farm.service import get_accessible_farm
from ..inventory.models import InventoryBalance
from ..livestock.models import LivestockBatch
from ..crop.models import CropCycle
from ..trade.service import trade_summary
from sqlalchemy import func


def recent_months(reference, count=6):
    months = []
    month_index = reference.year * 12 + reference.month - 1
    for offset in range(count - 1, -1, -1):
        value = month_index - offset
        year, zero_based_month = divmod(value, 12)
        months.append(f"{year:04d}-{zero_based_month + 1:02d}")
    return months


def system_overview(now=None):
    now = now or datetime.now()
    rows = db.session.execute(
        select(User.created_at, User.last_login_at, User.role, User.is_active)
    ).all()

    months = recent_months(now)
    month_counts = Counter(
        created_at.strftime("%Y-%m")
        for created_at, _last_login_at, _role, _is_active in rows
        if created_at is not None
    )
    role_counts = Counter(role for _created_at, _last_login_at, role, _is_active in rows)
    recent_threshold = now - timedelta(days=7)

    return {
        "summary": {
            "registeredUsers": len(rows),
            "activeUsers": sum(1 for row in rows if row.is_active),
            "recentLogins": sum(
                1 for row in rows if row.last_login_at is not None and row.last_login_at >= recent_threshold
            ),
            "serviceHealthy": True,
        },
        "registrationTrend": [
            {"month": month, "count": month_counts.get(month, 0)} for month in months
        ],
        "roleDistribution": [
            {"role": role, "count": count} for role, count in sorted(role_counts.items())
        ],
        "generatedAt": now.isoformat(timespec="seconds"),
    }


def farm_overview(farm_id, actor):
    get_accessible_farm(farm_id, actor)
    inventory = db.session.execute(select(func.coalesce(func.sum(InventoryBalance.quantity * InventoryBalance.average_cost), 0), func.count(InventoryBalance.id)).where(InventoryBalance.farm_id == farm_id, InventoryBalance.quantity > 0)).one()
    return {
        "farmId": farm_id,
        "inventory": {"stockValue": f"{inventory[0]:.2f}", "activeItemCount": inventory[1]},
        "livestock": {"activeBatchCount": db.session.scalar(select(func.count(LivestockBatch.id)).where(LivestockBatch.farm_id == farm_id, LivestockBatch.status == "ACTIVE")) or 0},
        "crops": {"openCycleCount": db.session.scalar(select(func.count(CropCycle.id)).where(CropCycle.farm_id == farm_id, CropCycle.status.in_(("PLANNED", "ACTIVE", "HARVESTING")))) or 0},
        "trade": trade_summary(farm_id, actor),
    }
