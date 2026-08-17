from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...core.errors import ApiError
from ...extensions import db
from ..auth.service import format_datetime
from .models import CropType, CropVariety, LivestockSpecies, Unit


def _decimal_text(value):
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def unit_payload(unit):
    return {
        "id": unit.id,
        "code": unit.code,
        "name": unit.name,
        "dimension": unit.dimension,
        "baseFactor": _decimal_text(unit.base_factor),
        "scale": unit.scale,
        "isActive": unit.is_active,
    }


def variety_payload(variety):
    return {
        "id": variety.id,
        "cropTypeId": variety.crop_type_id,
        "code": variety.code,
        "name": variety.name,
        "isActive": variety.is_active,
        "createdAt": format_datetime(variety.created_at),
        "updatedAt": format_datetime(variety.updated_at),
    }


def list_catalogs(actor):
    visible = () if actor.role == "admin" else (True,)
    unit_statement = select(Unit)
    species_statement = select(LivestockSpecies)
    crop_statement = select(CropType)
    variety_statement = select(CropVariety)
    if visible:
        unit_statement = unit_statement.where(Unit.is_active.is_(True))
        species_statement = species_statement.where(LivestockSpecies.is_active.is_(True))
        crop_statement = crop_statement.where(CropType.is_active.is_(True))
        variety_statement = variety_statement.where(CropVariety.is_active.is_(True))

    units = db.session.scalars(unit_statement.order_by(Unit.dimension, Unit.id)).all()
    species = db.session.scalars(species_statement.order_by(LivestockSpecies.id)).all()
    crop_types = db.session.scalars(crop_statement.order_by(CropType.id)).all()
    varieties = db.session.scalars(variety_statement.order_by(CropVariety.crop_type_id, CropVariety.name)).all()
    varieties_by_type = {}
    for variety in varieties:
        varieties_by_type.setdefault(variety.crop_type_id, []).append(variety_payload(variety))

    return {
        "units": [unit_payload(unit) for unit in units],
        "livestockSpecies": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "trackingMode": item.tracking_mode,
                "isActive": item.is_active,
            }
            for item in species
        ],
        "cropTypes": [
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "isActive": item.is_active,
                "varieties": varieties_by_type.get(item.id, []),
            }
            for item in crop_types
        ],
    }


def _active_crop_type(crop_type_id):
    crop_type = db.session.get(CropType, crop_type_id)
    if crop_type is None:
        raise ApiError("作物类型不存在", 404, "CROP_TYPE_NOT_FOUND")
    if not crop_type.is_active:
        raise ApiError("作物类型已停用", 409, "CROP_TYPE_DISABLED")
    return crop_type


def create_crop_variety(payload, actor):
    _active_crop_type(payload.crop_type_id)
    variety = CropVariety(
        crop_type_id=payload.crop_type_id,
        code=payload.code,
        name=payload.name,
        created_by_id=actor.id,
        updated_by_id=actor.id,
    )
    db.session.add(variety)
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该作物下的品种编号已存在", 409, "CROP_VARIETY_CODE_EXISTS", "code") from error
    return variety_payload(variety)


def update_crop_variety(variety_id, payload, actor):
    variety = db.session.get(CropVariety, variety_id)
    if variety is None:
        raise ApiError("作物品种不存在", 404, "CROP_VARIETY_NOT_FOUND")
    if "crop_type_id" in payload.model_fields_set:
        _active_crop_type(payload.crop_type_id)
    for field in ("crop_type_id", "code", "name", "is_active"):
        if field in payload.model_fields_set:
            setattr(variety, field, getattr(payload, field))
    variety.updated_by_id = actor.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ApiError("该作物下的品种编号已存在", 409, "CROP_VARIETY_CODE_EXISTS", "code") from error
    return variety_payload(variety)
