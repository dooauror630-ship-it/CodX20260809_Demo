from decimal import Decimal

from sqlalchemy import select

from ...extensions import db
from .models import CropType, LivestockSpecies, Unit


DEFAULT_UNITS = (
    ("KG", "千克", "WEIGHT", Decimal("1"), 3),
    ("JIN", "斤", "WEIGHT", Decimal("0.5"), 3),
    ("TON", "吨", "WEIGHT", Decimal("1000"), 3),
    ("L", "升", "VOLUME", Decimal("1"), 3),
    ("HEAD", "头", "LIVESTOCK", Decimal("1"), 0),
    ("BIRD", "只", "LIVESTOCK", Decimal("1"), 0),
    ("MU", "亩", "AREA", Decimal("1"), 3),
    ("BAG", "袋", "PACKAGE", Decimal("1"), 0),
)
DEFAULT_LIVESTOCK_SPECIES = (("PIG", "猪"), ("CHICKEN", "鸡"))
DEFAULT_CROP_TYPES = (
    ("TOBACCO", "烟草"),
    ("GARLIC", "大蒜"),
    ("RICE", "水稻"),
    ("RAPESEED", "油菜"),
)
DEFAULT_CROP_OPERATION_TEMPLATES = {
    "GARLIC": (
        ("LAND_PREPARATION", 0, True, "完成整地并确认墒情"),
        ("SOWING", 7, True, "完成播种并记录作业面积"),
        ("WEEDING", 35, False, "检查杂草并按需除草"),
        ("FERTILIZATION", 45, True, "根据长势安排追肥"),
        ("IRRIGATION", 60, False, "检查墒情并按需灌溉"),
        ("PEST_CONTROL", 75, False, "巡查病虫害并按需防治"),
    ),
    "RICE": (
        ("LAND_PREPARATION", 0, True, "完成整地与田面准备"),
        ("SOWING", 7, True, "完成育秧播种"),
        ("TRANSPLANTING", 30, True, "完成移栽并记录作业面积"),
        ("IRRIGATION", 32, True, "移栽后检查水层"),
        ("FERTILIZATION", 45, True, "根据苗情安排追肥"),
        ("PEST_CONTROL", 60, False, "巡查病虫害并按需防治"),
    ),
    "RAPESEED": (
        ("LAND_PREPARATION", 0, True, "完成整地与开沟"),
        ("SOWING", 7, True, "完成播种并记录作业面积"),
        ("WEEDING", 30, False, "检查杂草并按需除草"),
        ("FERTILIZATION", 45, True, "根据长势安排追肥"),
        ("PEST_CONTROL", 60, False, "巡查病虫害并按需防治"),
    ),
}


def seed_default_catalogs():
    from ..crop.models import CropOperationTemplate

    existing_units = set(db.session.scalars(select(Unit.code)).all())
    existing_species = set(db.session.scalars(select(LivestockSpecies.code)).all())
    existing_crops = set(db.session.scalars(select(CropType.code)).all())

    for code, name, dimension, base_factor, scale in DEFAULT_UNITS:
        if code not in existing_units:
            db.session.add(Unit(
                code=code,
                name=name,
                dimension=dimension,
                base_factor=base_factor,
                scale=scale,
            ))
    for code, name in DEFAULT_LIVESTOCK_SPECIES:
        if code not in existing_species:
            db.session.add(LivestockSpecies(code=code, name=name))
    for code, name in DEFAULT_CROP_TYPES:
        if code not in existing_crops:
            db.session.add(CropType(code=code, name=name))
    db.session.commit()

    crop_type_ids = dict(db.session.execute(select(CropType.code, CropType.id)).all())
    existing_templates = set(db.session.execute(select(
        CropOperationTemplate.crop_type_id, CropOperationTemplate.operation_type,
    )).all())
    for crop_code, templates in DEFAULT_CROP_OPERATION_TEMPLATES.items():
        crop_type_id = crop_type_ids[crop_code]
        for operation_type, offset_days, required, default_notes in templates:
            if (crop_type_id, operation_type) not in existing_templates:
                db.session.add(CropOperationTemplate(
                    crop_type_id=crop_type_id,
                    operation_type=operation_type,
                    offset_days=offset_days,
                    required=required,
                    default_notes=default_notes,
                ))
    db.session.commit()
