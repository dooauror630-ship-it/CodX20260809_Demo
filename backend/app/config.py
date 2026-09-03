import json
import os
import secrets
import ssl
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus


BACKEND_DIR = Path(__file__).resolve().parents[1]
INSTANCE_DIR = BACKEND_DIR / "instance"


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_secret_key():
    configured_key = os.getenv("AGRI_SECRET_KEY")
    if configured_key:
        return configured_key

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    secret_file = INSTANCE_DIR / "secret_key"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
    return secret_file.read_text(encoding="utf-8").strip()


def get_mysql_config():
    config_file = Path(os.getenv("AGRI_MYSQL_CONFIG", INSTANCE_DIR / "mysql.json"))
    file_config = (
        json.loads(config_file.read_text(encoding="utf-8"))
        if config_file.exists()
        else {}
    )
    config = {
        "host": os.getenv("AGRI_MYSQL_HOST", file_config.get("host", "127.0.0.1")),
        "port": int(os.getenv("AGRI_MYSQL_PORT", file_config.get("port", 3306))),
        "user": os.getenv("AGRI_MYSQL_USER", file_config.get("user")),
        "password": os.getenv("AGRI_MYSQL_PASSWORD", file_config.get("password")),
        "database": os.getenv("AGRI_MYSQL_DATABASE", file_config.get("database")),
        "ssl": env_bool("AGRI_MYSQL_SSL", bool(file_config.get("ssl", True))),
    }
    missing = [key for key in ("user", "password", "database") if not config[key]]
    if missing:
        raise RuntimeError(f"Missing MySQL settings: {', '.join(missing)}")
    return config


def configure_app(app, test_config=None):
    app.config.from_mapping(
        DATABASE_ENGINE=os.getenv("AGRI_DATABASE_ENGINE", "mysql"),
        DATABASE=os.getenv("AGRI_DATABASE", str(INSTANCE_DIR / "agriculture.db")),
        SECRET_KEY=get_secret_key(),
        PERMANENT_SESSION_LIFETIME=timedelta(days=7),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=env_bool("AGRI_COOKIE_SECURE"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        ALLOW_SELF_REGISTRATION=env_bool("AGRI_ALLOW_SELF_REGISTRATION", True),
        AGENT_API_KEY=os.getenv("AGRI_AGENT_API_KEY", ""),
        AGENT_FARM_CODE=os.getenv("AGRI_AGENT_FARM_CODE", "AGENT-DEMO"),
        SKIP_SCHEMA_CHECK=env_bool("AGRI_SKIP_SCHEMA_CHECK"),
    )
    if test_config:
        app.config.update(test_config)

    engine = app.config["DATABASE_ENGINE"]
    if engine == "sqlite":
        database_path = Path(app.config["DATABASE"]).resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path.as_posix()}"
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"connect_args": {"check_same_thread": False}}
        return

    if engine != "mysql":
        raise RuntimeError(f"Unsupported database engine: {engine}")

    mysql = app.config.get("MYSQL_CONFIG") or get_mysql_config()
    app.config["MYSQL_CONFIG"] = mysql
    username = quote_plus(mysql["user"])
    password = quote_plus(mysql["password"])
    database = quote_plus(mysql["database"])
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{username}:{password}@{mysql['host']}:{mysql['port']}/{database}"
        "?charset=utf8mb4"
    )
    connect_args = {
        "connect_timeout": 5,
        "read_timeout": 10,
        "write_timeout": 10,
    }
    if mysql["ssl"]:
        connect_args["ssl"] = {
            "verify_mode": ssl.CERT_NONE,
            "check_hostname": False,
        }
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "connect_args": connect_args,
    }
