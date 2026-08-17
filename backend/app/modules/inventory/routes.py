from flask import Blueprint, g, request

from ...core.errors import success_response
from ...core.security import admin_required, login_required
from ..auth.schemas import parse_payload
from .schemas import (
    CategoryListQuery,
    CreateCategoryPayload,
    CreateItemPayload,
    CreateWarehousePayload,
    ItemListQuery,
    UpdateCategoryPayload,
    UpdateItemPayload,
    UpdateWarehousePayload,
    WarehouseListQuery,
)
from .purchase_schemas import (
    CreateProductionStockOperationPayload,
    CreatePurchasePayload,
    CreatePurchaseReturnPayload,
    CreateStockTransferPayload,
    CreateSupplierPayload,
    PurchaseActionPayload,
    PurchaseListQuery,
    StockLedgerQuery,
    StockListQuery,
    SupplierListQuery,
    UpdatePurchasePayload,
    UpdateSupplierPayload,
)
from .inventory_count_schemas import (
    CreateInventoryCountPayload,
    InventoryCountActionPayload,
    InventoryCountListQuery,
    UpdateInventoryCountPayload,
)
from .inventory_count_service import (
    cancel_inventory_count,
    create_inventory_count,
    inventory_count_detail,
    list_inventory_counts,
    post_inventory_count,
    update_inventory_count,
)
from .inventory_analysis_schemas import InventoryAnalysisQuery
from .inventory_analysis_service import inventory_analysis
from .purchase_service import (
    cancel_purchase,
    create_production_stock_operation,
    create_purchase,
    create_purchase_return,
    create_supplier,
    create_stock_transfer,
    list_purchases,
    list_stock_ledger,
    list_stocks,
    list_suppliers,
    post_purchase,
    purchase_detail,
    update_purchase,
    update_supplier,
)
from .service import (
    create_category,
    create_item,
    create_warehouse,
    list_categories,
    list_items,
    list_warehouses,
    update_category,
    update_item,
    update_warehouse,
)


inventory_bp = Blueprint("inventory", __name__)


@inventory_bp.get("/warehouses")
@login_required
def warehouses():
    query = parse_payload(WarehouseListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_warehouses(query, g.current_user))


@inventory_bp.post("/warehouses")
@admin_required
def add_warehouse():
    payload = parse_payload(CreateWarehousePayload, request.get_json(silent=True), "仓库信息格式错误")
    return success_response({"warehouse": create_warehouse(payload, g.current_user)}, "仓库已创建", 201)


@inventory_bp.patch("/warehouses/<int:warehouse_id>")
@admin_required
def edit_warehouse(warehouse_id):
    payload = parse_payload(UpdateWarehousePayload, request.get_json(silent=True), "仓库信息格式错误")
    return success_response(
        {"warehouse": update_warehouse(warehouse_id, payload, g.current_user)},
        "仓库信息已更新",
    )


@inventory_bp.get("/item-categories")
@login_required
def item_categories():
    query = parse_payload(CategoryListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_categories(query, g.current_user))


@inventory_bp.post("/item-categories")
@admin_required
def add_item_category():
    payload = parse_payload(CreateCategoryPayload, request.get_json(silent=True), "物料分类格式错误")
    return success_response({"category": create_category(payload, g.current_user)}, "物料分类已创建", 201)


@inventory_bp.patch("/item-categories/<int:category_id>")
@admin_required
def edit_item_category(category_id):
    payload = parse_payload(UpdateCategoryPayload, request.get_json(silent=True), "物料分类格式错误")
    return success_response(
        {"category": update_category(category_id, payload, g.current_user)},
        "物料分类已更新",
    )


@inventory_bp.get("/items")
@login_required
def items():
    query = parse_payload(ItemListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_items(query, g.current_user))


@inventory_bp.post("/items")
@admin_required
def add_item():
    payload = parse_payload(CreateItemPayload, request.get_json(silent=True), "物料信息格式错误")
    return success_response({"item": create_item(payload, g.current_user)}, "物料已创建", 201)


@inventory_bp.patch("/items/<int:item_id>")
@admin_required
def edit_item(item_id):
    payload = parse_payload(UpdateItemPayload, request.get_json(silent=True), "物料信息格式错误")
    return success_response({"item": update_item(item_id, payload, g.current_user)}, "物料信息已更新")


@inventory_bp.get("/suppliers")
@login_required
def suppliers():
    query = parse_payload(SupplierListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_suppliers(query, g.current_user))


@inventory_bp.post("/suppliers")
@login_required
def add_supplier():
    payload = parse_payload(CreateSupplierPayload, request.get_json(silent=True), "供应商信息格式错误")
    return success_response({"supplier": create_supplier(payload, g.current_user)}, "供应商已创建", 201)


@inventory_bp.patch("/suppliers/<int:supplier_id>")
@login_required
def edit_supplier(supplier_id):
    payload = parse_payload(UpdateSupplierPayload, request.get_json(silent=True), "供应商信息格式错误")
    return success_response({"supplier": update_supplier(supplier_id, payload, g.current_user)}, "供应商已更新")


@inventory_bp.get("/purchases")
@login_required
def purchases():
    query = parse_payload(PurchaseListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_purchases(query, g.current_user))


@inventory_bp.get("/purchases/<int:purchase_id>")
@login_required
def purchase(purchase_id):
    return success_response({"purchase": purchase_detail(purchase_id, g.current_user)})


@inventory_bp.post("/purchases")
@login_required
def add_purchase():
    payload = parse_payload(CreatePurchasePayload, request.get_json(silent=True), "采购单格式错误")
    return success_response({"purchase": create_purchase(payload, g.current_user)}, "采购草稿已创建", 201)


@inventory_bp.patch("/purchases/<int:purchase_id>")
@login_required
def edit_purchase(purchase_id):
    payload = parse_payload(UpdatePurchasePayload, request.get_json(silent=True), "采购单格式错误")
    return success_response({"purchase": update_purchase(purchase_id, payload, g.current_user)}, "采购草稿已更新")


@inventory_bp.post("/purchases/<int:purchase_id>/post")
@login_required
def post_purchase_order(purchase_id):
    payload = parse_payload(PurchaseActionPayload, request.get_json(silent=True), "采购单版本无效")
    return success_response({"purchase": post_purchase(purchase_id, payload, g.current_user)}, "采购单已过账")


@inventory_bp.post("/purchases/<int:purchase_id>/cancel")
@login_required
def cancel_purchase_order(purchase_id):
    payload = parse_payload(PurchaseActionPayload, request.get_json(silent=True), "采购单版本无效")
    return success_response({"purchase": cancel_purchase(purchase_id, payload, g.current_user)}, "采购单已取消")


@inventory_bp.post("/purchase-returns")
@login_required
def add_purchase_return():
    payload = parse_payload(CreatePurchaseReturnPayload, request.get_json(silent=True), "采购退货单格式错误")
    purchase_return, created = create_purchase_return(payload, g.current_user)
    return success_response(
        {"purchaseReturn": purchase_return},
        "采购退货已过账" if created else "该采购退货单已过账",
        201 if created else 200,
    )


@inventory_bp.get("/stocks")
@login_required
def stocks():
    query = parse_payload(StockListQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_stocks(query, g.current_user))


@inventory_bp.get("/stock-ledger")
@login_required
def stock_ledger():
    query = parse_payload(StockLedgerQuery, request.args.to_dict(), "筛选条件格式错误")
    return success_response(list_stock_ledger(query, g.current_user))


@inventory_bp.get("/inventory-analysis")
@login_required
def inventory_analysis_overview():
    query = parse_payload(InventoryAnalysisQuery, request.args.to_dict(), "库存分析条件格式错误")
    return success_response(inventory_analysis(query, g.current_user))


@inventory_bp.get("/inventory-counts")
@login_required
def inventory_counts():
    query = parse_payload(InventoryCountListQuery, request.args.to_dict(), "盘点筛选条件格式错误")
    return success_response(list_inventory_counts(query, g.current_user))


@inventory_bp.get("/inventory-counts/<int:count_id>")
@login_required
def inventory_count(count_id):
    return success_response({"inventoryCount": inventory_count_detail(count_id, g.current_user)})


@inventory_bp.post("/inventory-counts")
@login_required
def add_inventory_count():
    payload = parse_payload(CreateInventoryCountPayload, request.get_json(silent=True), "盘点单格式错误")
    return success_response(
        {"inventoryCount": create_inventory_count(payload, g.current_user)},
        "盘点单已生成",
        201,
    )


@inventory_bp.patch("/inventory-counts/<int:count_id>")
@login_required
def edit_inventory_count(count_id):
    payload = parse_payload(UpdateInventoryCountPayload, request.get_json(silent=True), "盘点明细格式错误")
    return success_response(
        {"inventoryCount": update_inventory_count(count_id, payload, g.current_user)},
        "盘点草稿已保存",
    )


@inventory_bp.post("/inventory-counts/<int:count_id>/post")
@login_required
def post_inventory_count_document(count_id):
    payload = parse_payload(InventoryCountActionPayload, request.get_json(silent=True), "盘点操作格式错误")
    return success_response(
        {"inventoryCount": post_inventory_count(count_id, payload, g.current_user)},
        "盘点单已过账",
    )


@inventory_bp.post("/inventory-counts/<int:count_id>/cancel")
@login_required
def cancel_inventory_count_document(count_id):
    payload = parse_payload(InventoryCountActionPayload, request.get_json(silent=True), "盘点操作格式错误")
    return success_response(
        {"inventoryCount": cancel_inventory_count(count_id, payload, g.current_user)},
        "盘点单已取消",
    )


@inventory_bp.post("/stock-transfers")
@login_required
def add_stock_transfer():
    payload = parse_payload(CreateStockTransferPayload, request.get_json(silent=True), "调拨单格式错误")
    transfer, created = create_stock_transfer(payload, g.current_user)
    return success_response(
        {"transfer": transfer},
        "库存调拨已过账" if created else "该调拨单已过账",
        201 if created else 200,
    )


@inventory_bp.post("/production-stock-operations")
@login_required
def add_production_stock_operation():
    payload = parse_payload(
        CreateProductionStockOperationPayload,
        request.get_json(silent=True),
        "生产领退料单格式错误",
    )
    operation, created = create_production_stock_operation(payload, g.current_user)
    return success_response(
        {"operation": operation},
        "生产领退料已过账" if created else "该生产领退料单已过账",
        201 if created else 200,
    )
