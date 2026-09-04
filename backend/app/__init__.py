import os
from pathlib import Path

import click
from flask import Flask
from sqlalchemy import inspect, text

from .config import BACKEND_DIR, INSTANCE_DIR, configure_app
from .core.errors import register_error_handlers
from .core.security import init_security
from .extensions import db, migrate


REQUIRED_SCHEMA_REVISION = "0022_workflow_audit"


REQUIRED_SCHEMA = {
    "alembic_version": {"version_num"},
    "users": {
        "id", "username", "display_name", "password_hash", "role", "is_active",
        "created_at", "updated_at", "last_login_at",
    },
    "farms": {
        "id", "code", "name", "owner_name", "address", "timezone", "is_active",
        "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "farm_users": {
        "id", "farm_id", "user_id", "role_code", "is_active", "created_at", "updated_at",
    },
    "barns": {
        "id", "farm_id", "code", "name", "barn_type", "capacity", "is_active",
        "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "plots": {
        "id", "farm_id", "code", "name", "area_mu", "soil_type", "is_active",
        "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "units": {
        "id", "code", "name", "dimension", "base_factor", "scale", "is_active",
        "created_at", "updated_at",
    },
    "livestock_species": {
        "id", "code", "name", "tracking_mode", "is_active", "created_at", "updated_at",
    },
    "crop_types": {
        "id", "code", "name", "is_active", "created_at", "updated_at",
    },
    "crop_varieties": {
        "id", "crop_type_id", "code", "name", "is_active", "created_by_id",
        "updated_by_id", "created_at", "updated_at",
    },
    "warehouses": {
        "id", "farm_id", "code", "name", "location", "is_active", "created_by_id",
        "updated_by_id", "created_at", "updated_at",
    },
    "item_categories": {
        "id", "farm_id", "parent_id", "code", "name", "is_active", "created_by_id",
        "updated_by_id", "created_at", "updated_at",
    },
    "items": {
        "id", "farm_id", "category_id", "unit_id", "code", "name", "item_type",
        "safety_stock", "lot_tracking", "is_active", "created_by_id", "updated_by_id",
        "created_at", "updated_at",
    },
    "suppliers": {
        "id", "farm_id", "code", "name", "contact", "phone", "address", "is_active",
        "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "purchase_orders": {
        "id", "farm_id", "order_no", "supplier_id", "warehouse_id", "order_date", "status",
        "total_amount", "notes", "version", "posted_at", "posted_by_id", "created_by_id",
        "updated_by_id", "created_at", "updated_at",
    },
    "purchase_order_lines": {
        "id", "purchase_order_id", "item_id", "quantity", "unit_price", "amount", "lot_no", "expires_on",
    },
    "stock_documents": {
        "id", "farm_id", "document_no", "document_type", "from_warehouse_id", "to_warehouse_id",
        "status", "source_type", "source_id", "occurred_at", "created_by_id", "created_at",
    },
    "stock_movement_lines": {
        "id", "stock_document_id", "warehouse_id", "item_id", "quantity_delta", "unit_cost",
        "lot_no", "expires_on", "cost_object_type", "cost_object_id", "created_at",
    },
    "inventory_balances": {
        "id", "farm_id", "warehouse_id", "item_id", "quantity", "average_cost", "created_at", "updated_at",
    },
    "inventory_counts": {
        "id", "farm_id", "count_no", "warehouse_id", "count_date", "status", "notes", "version",
        "posted_at", "posted_by_id", "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "inventory_count_lines": {
        "id", "inventory_count_id", "item_id", "lot_no", "expires_on", "book_quantity",
        "actual_quantity", "difference_quantity", "unit_cost", "reason",
    },
    "livestock_batches": {
        "id", "farm_id", "species_id", "batch_no", "name", "entry_date", "source", "status",
        "closed_at", "notes", "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "livestock_movements": {
        "id", "farm_id", "batch_id", "movement_no", "movement_type", "from_barn_id", "to_barn_id",
        "quantity", "occurred_on", "reason", "notes", "created_by_id", "created_at",
    },
    "livestock_health_records": {
        "id", "farm_id", "batch_id", "record_no", "record_type", "occurred_on",
        "description", "medicine_name", "dosage", "notes", "created_by_id", "created_at",
    },
    "livestock_weight_records": {
        "id", "farm_id", "batch_id", "record_no", "occurred_on", "sample_count",
        "average_weight", "notes", "created_by_id", "created_at",
    },
    "cost_entries": {
        "id", "farm_id", "livestock_batch_id", "entry_no", "business_date", "cost_type",
        "amount", "description", "notes", "status", "cancelled_at", "cancelled_by_id",
        "created_by_id", "created_at",
    },
    "crop_cycles": {
        "id", "farm_id", "cycle_code", "plot_id", "crop_type_id", "variety_id", "area_mu",
        "planned_start_date", "planned_end_date", "actual_start_date", "actual_end_date", "status",
        "notes", "created_by_id", "updated_by_id", "created_at", "updated_at",
    },
    "crop_operation_templates": {
        "id", "crop_type_id", "operation_type", "offset_days", "required", "default_notes", "created_at",
    },
    "field_operations": {
        "id", "farm_id", "crop_cycle_id", "operation_type", "operation_date", "area_mu",
        "labor_hours", "machine_hours", "labor_cost", "service_cost", "notes", "created_by_id", "created_at",
    },
    "harvest_batches": {
        "id", "farm_id", "crop_cycle_id", "harvest_no", "harvest_date", "gross_weight", "net_weight",
        "unit_id", "warehouse_id", "notes", "created_by_id", "created_at",
    },
    "tobacco_curing_batches": {
        "id", "farm_id", "crop_cycle_id", "curing_no", "start_at", "end_at", "input_weight",
        "output_weight", "unit_id", "fuel_cost", "electricity_cost", "status", "notes",
        "created_by_id", "completed_by_id", "created_at",
    },
    "grading_records": {
        "id", "farm_id", "harvest_batch_id", "grade_code", "quantity", "unit_price_reference",
        "notes", "created_by_id", "created_at",
    },
    "field_operation_inputs": {
        "id", "farm_id", "field_operation_id", "stock_document_id", "item_id", "quantity", "amount",
        "created_by_id", "created_at",
    },
    "customers": {"id", "farm_id", "code", "name", "contact", "phone", "address", "is_active", "created_by_id", "updated_by_id", "created_at", "updated_at"},
    "sales_orders": {"id", "farm_id", "order_no", "customer_id", "warehouse_id", "sale_date", "status", "total_amount", "received_amount", "notes", "posted_at", "posted_by_id", "created_by_id", "created_at"},
    "sales_order_lines": {"id", "sales_order_id", "item_id", "quantity", "unit_price", "amount", "unit_cost"},
    "payments": {"id", "farm_id", "payment_no", "direction", "business_date", "amount", "method", "customer_id", "sales_order_id", "notes", "created_by_id", "created_at"},
    "sales_returns": {"id", "farm_id", "return_no", "sales_order_id", "return_date", "status", "total_amount", "created_by_id", "created_at"},
    "sales_return_lines": {"id", "sales_return_id", "sales_order_line_id", "quantity", "amount", "unit_cost"},
    "farm_tasks": {"id", "farm_id", "task_no", "title", "due_date", "status", "notes", "created_by_id", "completed_by_id", "completed_at", "created_at"},
    "audit_logs": {"id", "farm_id", "actor_id", "action", "resource_type", "resource_id", "detail", "created_at"},
}


def verify_database_schema():
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    for table_name, required_columns in REQUIRED_SCHEMA.items():
        if table_name not in table_names:
            raise RuntimeError(f"Database migration is required; missing table: {table_name}")
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        missing = required_columns - columns
        if missing:
            raise RuntimeError(
                f"Database migration is required; missing {table_name} columns: {', '.join(sorted(missing))}"
            )
    revision = db.session.scalar(text("SELECT version_num FROM alembic_version"))
    if revision != REQUIRED_SCHEMA_REVISION:
        raise RuntimeError(
            f"Database migration is required; expected {REQUIRED_SCHEMA_REVISION}, found {revision or 'none'}"
        )


def create_app(test_config=None):
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__, instance_path=str(INSTANCE_DIR), instance_relative_config=False)
    configure_app(app, test_config)
    app.json.ensure_ascii = False

    db.init_app(app)

    from .modules.auth import models as _auth_models  # noqa: F401
    from .modules.catalog import models as _catalog_models  # noqa: F401
    from .modules.crop import models as _crop_models  # noqa: F401
    from .modules.farm import models as _farm_models  # noqa: F401
    from .modules.inventory import models as _inventory_models  # noqa: F401
    from .modules.livestock import models as _livestock_models  # noqa: F401
    from .modules.trade import models as _trade_models  # noqa: F401
    from .modules.workflow import models as _workflow_models  # noqa: F401

    migrate.init_app(app, db, directory=str(Path(BACKEND_DIR) / "migrations"))
    register_error_handlers(app)
    init_security(app)

    from .modules.admin import admin_bp
    from .modules.agent import agent_bp
    from .modules.analytics import analytics_bp
    from .modules.auth import auth_bp
    from .modules.catalog import catalog_bp
    from .modules.crop import crop_bp
    from .modules.farm import farm_bp
    from .modules.inventory import inventory_bp
    from .modules.livestock import livestock_bp
    from .modules.trade import trade_bp
    from .modules.workflow import workflow_bp
    from .modules.system import system_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(auth_bp, url_prefix="/api/auth", name_prefix="legacy")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(agent_bp, url_prefix="/api/v1/agent")
    app.register_blueprint(analytics_bp, url_prefix="/api/v1/analytics")
    app.register_blueprint(farm_bp, url_prefix="/api/v1")
    app.register_blueprint(catalog_bp, url_prefix="/api/v1")
    app.register_blueprint(crop_bp, url_prefix="/api/v1")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1")
    app.register_blueprint(livestock_bp, url_prefix="/api/v1")
    app.register_blueprint(trade_bp, url_prefix="/api/v1")
    app.register_blueprint(workflow_bp, url_prefix="/api/v1")
    app.register_blueprint(system_bp)

    with app.app_context():
        if app.config["DATABASE_ENGINE"] == "sqlite":
            db.create_all()
            from .modules.catalog.seed import seed_default_catalogs

            seed_default_catalogs()
        elif not app.config["SKIP_SCHEMA_CHECK"]:
            verify_database_schema()

    @app.cli.command("schema-check")
    def schema_check_command():
        verify_database_schema()
        click.echo("Database schema is ready.")

    @app.cli.command("bootstrap-admin")
    @click.option("--username", default="admin", show_default=True)
    @click.option("--display-name", default="系统管理员", show_default=True)
    def bootstrap_admin_command(username, display_name):
        password = os.getenv("AGRI_BOOTSTRAP_ADMIN_PASSWORD")
        if not password:
            raise click.ClickException("Set AGRI_BOOTSTRAP_ADMIN_PASSWORD before running this command.")
        from .modules.auth.service import ensure_admin_user

        user, created = ensure_admin_user(username, password, display_name)
        action = "created" if created else "updated"
        click.echo(f"Admin account '{user.username}' was {action}.")

    @app.cli.command("inventory-reconcile")
    @click.option("--farm-id", type=int)
    def inventory_reconcile_command(farm_id):
        from .modules.inventory.purchase_service import reconcile_inventory

        discrepancies = reconcile_inventory(farm_id)
        if discrepancies:
            raise click.ClickException(f"Inventory reconciliation failed: {len(discrepancies)} discrepancy(s).")
        click.echo("Inventory balances match posted stock movements.")

    @app.cli.command("seed-agent-demo")
    def seed_agent_demo_command():
        from .modules.agent.seed import seed_agent_demo

        farm = seed_agent_demo()
        click.echo(f"Agent demo data is ready: farmId={farm.id}, code={farm.code}")

    return app


__all__ = ["create_app", "db"]
