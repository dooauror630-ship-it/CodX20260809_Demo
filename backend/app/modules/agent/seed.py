from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from ...extensions import db
from ..auth.models import User
from ..catalog.models import LivestockSpecies, Unit
from ..farm.models import Barn, Farm
from ..inventory.models import InventoryBalance, Item, ItemCategory, Warehouse
from ..livestock.models import (
    LivestockBatch,
    LivestockHealthRecord,
    LivestockMovement,
    LivestockWeightRecord,
)


def seed_agent_demo():
    actor = db.session.scalar(
        select(User).where(User.role == "admin", User.is_active.is_(True)).order_by(User.id)
    )
    if actor is None:
        raise RuntimeError("Create an active administrator before seeding agent demo data.")

    farm = db.session.scalar(select(Farm).where(Farm.code == "AGENT-DEMO"))
    if farm is None:
        farm = Farm(
            code="AGENT-DEMO",
            name="智能体接口测试农场",
            owner_name="测试负责人",
            address="测试数据，请勿用于生产核算",
            timezone="Asia/Shanghai",
            is_active=True,
            created_by_id=actor.id,
            updated_by_id=actor.id,
        )
        db.session.add(farm)
        db.session.flush()

    warehouse = db.session.scalar(
        select(Warehouse).where(Warehouse.farm_id == farm.id, Warehouse.code == "DEMO-WH")
    )
    if warehouse is None:
        warehouse = Warehouse(
            farm_id=farm.id,
            code="DEMO-WH",
            name="智能体测试仓库",
            location="测试区",
            is_active=True,
            created_by_id=actor.id,
            updated_by_id=actor.id,
        )
        db.session.add(warehouse)
        db.session.flush()

    category = db.session.scalar(
        select(ItemCategory).where(ItemCategory.farm_id == farm.id, ItemCategory.code == "DEMO-FEED")
    )
    if category is None:
        category = ItemCategory(
            farm_id=farm.id,
            code="DEMO-FEED",
            name="智能体测试物料",
            is_active=True,
            created_by_id=actor.id,
            updated_by_id=actor.id,
        )
        db.session.add(category)
        db.session.flush()

    unit = db.session.scalar(select(Unit).where(Unit.code == "KG"))
    pig_species = db.session.scalar(select(LivestockSpecies).where(LivestockSpecies.code == "PIG"))
    if unit is None or pig_species is None:
        raise RuntimeError("Default KG unit and PIG species are required.")

    item_specs = (
        ("DEMO-CORN", "测试玉米饲料", "500", "120", "2.50"),
        ("DEMO-VACCINE", "测试疫苗", "30", "10", "18.00"),
        ("DEMO-SOY", "测试豆粕", "100", "300", "4.20"),
    )
    for code, name, safety_stock, quantity, average_cost in item_specs:
        item = db.session.scalar(
            select(Item).where(Item.farm_id == farm.id, Item.code == code)
        )
        if item is None:
            item = Item(
                farm_id=farm.id,
                category_id=category.id,
                unit_id=unit.id,
                code=code,
                name=name,
                item_type="feed",
                safety_stock=Decimal(safety_stock),
                lot_tracking=False,
                is_active=True,
                created_by_id=actor.id,
                updated_by_id=actor.id,
            )
            db.session.add(item)
            db.session.flush()
        balance = db.session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.warehouse_id == warehouse.id,
                InventoryBalance.item_id == item.id,
            )
        )
        if balance is None:
            db.session.add(InventoryBalance(
                farm_id=farm.id,
                warehouse_id=warehouse.id,
                item_id=item.id,
                quantity=Decimal(quantity),
                average_cost=Decimal(average_cost),
            ))

    barn = db.session.scalar(
        select(Barn).where(Barn.farm_id == farm.id, Barn.code == "DEMO-PIG-01")
    )
    if barn is None:
        barn = Barn(
            farm_id=farm.id,
            code="DEMO-PIG-01",
            name="智能体测试育肥舍",
            barn_type="pig",
            capacity=200,
            is_active=True,
            created_by_id=actor.id,
            updated_by_id=actor.id,
        )
        db.session.add(barn)
        db.session.flush()

    today = date.today()
    batch = db.session.scalar(
        select(LivestockBatch).where(
            LivestockBatch.farm_id == farm.id,
            LivestockBatch.batch_no == "DEMO-PIG-001",
        )
    )
    if batch is None:
        batch = LivestockBatch(
            farm_id=farm.id,
            species_id=pig_species.id,
            batch_no="DEMO-PIG-001",
            name="智能体测试育肥猪",
            entry_date=today - timedelta(days=45),
            source="测试供应户",
            status="ACTIVE",
            notes="仅用于 Dify 接口测试",
            created_by_id=actor.id,
            updated_by_id=actor.id,
        )
        db.session.add(batch)
        db.session.flush()

    movements = (
        ("DEMO-ENTRY-001", "ENTRY", None, barn.id, 86, today - timedelta(days=45), "测试入栏"),
        ("DEMO-DEATH-001", "DEATH", barn.id, None, 2, today - timedelta(days=8), "测试死亡记录"),
    )
    for number, kind, from_barn, to_barn, quantity, occurred_on, reason in movements:
        exists = db.session.scalar(
            select(LivestockMovement.id).where(
                LivestockMovement.farm_id == farm.id,
                LivestockMovement.movement_no == number,
            )
        )
        if exists is None:
            db.session.add(LivestockMovement(
                farm_id=farm.id,
                batch_id=batch.id,
                movement_no=number,
                movement_type=kind,
                from_barn_id=from_barn,
                to_barn_id=to_barn,
                quantity=quantity,
                occurred_on=occurred_on,
                reason=reason,
                notes="Dify 测试数据",
                created_by_id=actor.id,
            ))

    health_specs = (
        ("DEMO-HEALTH-001", "VACCINATION", today - timedelta(days=20), "完成口蹄疫疫苗接种", "测试疫苗"),
        ("DEMO-HEALTH-002", "DISEASE", today - timedelta(days=5), "发现轻微咳嗽，已隔离观察", None),
    )
    for number, kind, occurred_on, description, medicine in health_specs:
        exists = db.session.scalar(
            select(LivestockHealthRecord.id).where(
                LivestockHealthRecord.farm_id == farm.id,
                LivestockHealthRecord.record_no == number,
            )
        )
        if exists is None:
            db.session.add(LivestockHealthRecord(
                farm_id=farm.id,
                batch_id=batch.id,
                record_no=number,
                record_type=kind,
                occurred_on=occurred_on,
                description=description,
                medicine_name=medicine,
                dosage="按测试说明" if medicine else None,
                notes="Dify 测试数据",
                created_by_id=actor.id,
            ))

    weight_exists = db.session.scalar(
        select(LivestockWeightRecord.id).where(
            LivestockWeightRecord.farm_id == farm.id,
            LivestockWeightRecord.record_no == "DEMO-WEIGHT-001",
        )
    )
    if weight_exists is None:
        db.session.add(LivestockWeightRecord(
            farm_id=farm.id,
            batch_id=batch.id,
            record_no="DEMO-WEIGHT-001",
            occurred_on=today - timedelta(days=3),
            sample_count=20,
            average_weight=Decimal("32.5"),
            notes="Dify 测试数据",
            created_by_id=actor.id,
        ))

    db.session.commit()
    return farm
