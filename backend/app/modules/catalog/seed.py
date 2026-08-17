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


def seed_default_catalogs():
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
