#!/usr/bin/env bash
set -euo pipefail

APP_ROOT=/opt/agriculture-management
APP_DIR="$APP_ROOT/app"
ENV_DIR=/etc/agriculture-management
BACKUP_DIR=/var/backups/agriculture-management

if [[ $EUID -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
fi
if [[ ! -f "$APP_DIR/backend/wsgi.py" || ! -f "$APP_DIR/frontend/dist/index.html" ]]; then
    echo "Application files are incomplete." >&2
    exit 1
fi

id agriculture >/dev/null 2>&1 || useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin agriculture
install -d -o agriculture -g agriculture -m 0750 "$APP_DIR/backend/instance"
install -d -o root -g agriculture -m 0750 "$ENV_DIR"
install -d -o root -g root -m 0700 "$BACKUP_DIR"

if [[ ! -f "$ENV_DIR/app.env" ]]; then
    APP_DB_PASSWORD=$(openssl rand -hex 24)
    MIGRATE_DB_PASSWORD=$(openssl rand -hex 24)
    APP_SECRET=$(openssl rand -hex 32)
    cat >"$ENV_DIR/app.env" <<EOF
AGRI_DATABASE_ENGINE=mysql
AGRI_MYSQL_HOST=127.0.0.1
AGRI_MYSQL_PORT=3306
AGRI_MYSQL_USER=agri_app
AGRI_MYSQL_PASSWORD=$APP_DB_PASSWORD
AGRI_MYSQL_DATABASE=agriculture_management
AGRI_MYSQL_SSL=0
AGRI_SECRET_KEY=$APP_SECRET
AGRI_COOKIE_SECURE=0
AGRI_ALLOW_SELF_REGISTRATION=0
EOF
    cat >"$ENV_DIR/migrate.env" <<EOF
AGRI_DATABASE_ENGINE=mysql
AGRI_MYSQL_HOST=127.0.0.1
AGRI_MYSQL_PORT=3306
AGRI_MYSQL_USER=agri_migrate
AGRI_MYSQL_PASSWORD=$MIGRATE_DB_PASSWORD
AGRI_MYSQL_DATABASE=agriculture_management
AGRI_MYSQL_SSL=0
AGRI_SECRET_KEY=$APP_SECRET
AGRI_SKIP_SCHEMA_CHECK=1
EOF
    chown root:agriculture "$ENV_DIR/app.env"
    chmod 0640 "$ENV_DIR/app.env"
    chown root:root "$ENV_DIR/migrate.env"
    chmod 0600 "$ENV_DIR/migrate.env"
fi

set -a
source "$ENV_DIR/app.env"
set +a
APP_PASSWORD=$AGRI_MYSQL_PASSWORD
set -a
source "$ENV_DIR/migrate.env"
set +a
MIGRATE_PASSWORD=$AGRI_MYSQL_PASSWORD

mysql --protocol=socket <<SQL
CREATE DATABASE IF NOT EXISTS agriculture_management CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'agri_app'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '$APP_PASSWORD';
ALTER USER 'agri_app'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '$APP_PASSWORD';
CREATE USER IF NOT EXISTS 'agri_migrate'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '$MIGRATE_PASSWORD';
ALTER USER 'agri_migrate'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '$MIGRATE_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON agriculture_management.* TO 'agri_app'@'127.0.0.1';
GRANT ALL PRIVILEGES ON agriculture_management.* TO 'agri_migrate'@'127.0.0.1';
FLUSH PRIVILEGES;
SQL

python3 -m venv "$APP_ROOT/venv"
"$APP_ROOT/venv/bin/python" -m pip install --upgrade pip
"$APP_ROOT/venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

set -a
source "$ENV_DIR/migrate.env"
set +a
cd "$APP_DIR"
"$APP_ROOT/venv/bin/python" -m flask --app backend.wsgi:app db upgrade

set -a
source "$ENV_DIR/app.env"
set +a
"$APP_ROOT/venv/bin/python" -m flask --app backend.wsgi:app schema-check

if [[ ! -f /root/agriculture-management-initial-admin-password ]]; then
    openssl rand -base64 24 | tr -d '\n' > /root/agriculture-management-initial-admin-password
    chmod 0600 /root/agriculture-management-initial-admin-password
fi
export AGRI_BOOTSTRAP_ADMIN_PASSWORD
AGRI_BOOTSTRAP_ADMIN_PASSWORD=$(cat /root/agriculture-management-initial-admin-password)
"$APP_ROOT/venv/bin/python" -m flask --app backend.wsgi:app bootstrap-admin --username admin --display-name "系统管理员"
unset AGRI_BOOTSTRAP_ADMIN_PASSWORD

install -o root -g root -m 0644 "$APP_DIR/deploy/ubuntu/agriculture-management.service" /etc/systemd/system/agriculture-management.service
install -o root -g root -m 0644 "$APP_DIR/deploy/ubuntu/nginx.conf" /etc/nginx/sites-available/agriculture-management
ln -sfn /etc/nginx/sites-available/agriculture-management /etc/nginx/sites-enabled/agriculture-management
rm -f /etc/nginx/sites-enabled/default

cat >/usr/local/sbin/agriculture-management-backup <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR=/var/backups/agriculture-management
install -d -o root -g root -m 0700 "$BACKUP_DIR"
mysqldump --protocol=socket --single-transaction --routines --triggers agriculture_management | gzip >"$BACKUP_DIR/agriculture_management-$(date +%Y%m%d-%H%M%S).sql.gz"
find "$BACKUP_DIR" -type f -name 'agriculture_management-*.sql.gz' -mtime +7 -delete
EOF
chmod 0750 /usr/local/sbin/agriculture-management-backup
printf '17 2 * * * root /usr/local/sbin/agriculture-management-backup\n' >/etc/cron.d/agriculture-management-backup
chmod 0644 /etc/cron.d/agriculture-management-backup

chown -R root:root "$APP_DIR" "$APP_ROOT/venv"
chown -R agriculture:agriculture "$APP_DIR/backend/instance"
nginx -t
systemctl daemon-reload
systemctl enable --now mysql nginx agriculture-management
systemctl reload nginx
/usr/local/sbin/agriculture-management-backup

echo "Deployment installed. Initial admin password is stored in /root/agriculture-management-initial-admin-password"
