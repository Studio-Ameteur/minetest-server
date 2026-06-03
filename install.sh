#!/bin/bash
# ===========================================
# СКРИПТ: install.sh
# Назначение: установка и настройка сервера Minetest
# Запуск: bash install.sh
# Требования: Ubuntu 20.04 / 22.04, права root
# ===========================================

set -e

# -------------------------------------------
# НАСТРОЙКИ
# Измените под ваш сервер
# -------------------------------------------
SERVER_DIR="/opt/minetest-server"
MINETEST_USER="minetest"
SERVICE_NAME="minetest"

# -------------------------------------------
# ЦВЕТА ДЛЯ ВЫВОДА
# -------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_ok()   { echo -e "${GREEN}[✓]${NC} $1"; }
log_err()  { echo -e "${RED}[✗]${NC} $1"; }
log_info() { echo -e "${YELLOW}[→]${NC} $1"; }

# -------------------------------------------
# ПРОВЕРКА ПРАВ
# -------------------------------------------
if [ "$EUID" -ne 0 ]; then
    log_err "Запустите скрипт с правами root: sudo bash install.sh"
    exit 1
fi

echo "==========================================="
echo "  Установка Minetest сервера"
echo "==========================================="

# -------------------------------------------
# УСТАНОВКА ЗАВИСИМОСТЕЙ
# -------------------------------------------
log_info "Обновление пакетов..."
apt update -q

log_info "Установка Minetest и зависимостей..."
apt install -y minetest-server git curl

log_ok "Зависимости установлены"

# -------------------------------------------
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ
# Сервер запускается от отдельного пользователя
# -------------------------------------------
if ! id "$MINETEST_USER" &>/dev/null; then
    log_info "Создание пользователя $MINETEST_USER..."
    useradd -r -m -s /bin/bash "$MINETEST_USER"
    log_ok "Пользователь создан"
fi

# -------------------------------------------
# КОПИРОВАНИЕ ФАЙЛОВ ПРОЕКТА
# -------------------------------------------
log_info "Копирование файлов сервера в $SERVER_DIR..."
mkdir -p "$SERVER_DIR"
cp -r . "$SERVER_DIR/"
chown -R "$MINETEST_USER:$MINETEST_USER" "$SERVER_DIR"
log_ok "Файлы скопированы"

# -------------------------------------------
# НАСТРОЙКА .env
# Создаём .env если его нет
# -------------------------------------------
if [ ! -f "$SERVER_DIR/.env" ]; then
    log_info "Создание .env из шаблона..."
    cp "$SERVER_DIR/.env.example" "$SERVER_DIR/.env"
    log_ok ".env создан — заполните реальными значениями: nano $SERVER_DIR/.env"
fi

# -------------------------------------------
# СОЗДАНИЕ SYSTEMD СЕРВИСА
# Сервер запускается автоматически при старте системы
# Управление: systemctl start/stop/restart minetest
# -------------------------------------------
log_info "Настройка systemd сервиса..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << SERVICE
[Unit]
Description=Minetest Game Server
After=network.target

[Service]
Type=simple
User=${MINETEST_USER}
WorkingDirectory=${SERVER_DIR}
ExecStart=/usr/bin/minetest --server --config ${SERVER_DIR}/config/minetest.conf
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
log_ok "Systemd сервис настроен"

# -------------------------------------------
# ИТОГ
# -------------------------------------------
echo ""
echo "==========================================="
log_ok "Установка завершена!"
echo "==========================================="
echo ""
echo "Следующие шаги:"
echo "  1. Заполните настройки: nano $SERVER_DIR/.env"
echo "  2. Запустите сервер:    systemctl start $SERVICE_NAME"
echo "  3. Статус сервера:      systemctl status $SERVICE_NAME"
echo "  4. Логи сервера:        journalctl -u $SERVICE_NAME -f"
echo ""
