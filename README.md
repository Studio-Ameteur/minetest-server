# minetest-server

Игровой сервер на базе [Minetest / Luanti](https://github.com/minetest/minetest) с интеграцией Laravel API, системой VIP-статусов и привилегий.

## Архитектура

Вся бизнес-логика реализована через Lua-моды — ядро Minetest не модифицируется. Это позволяет обновлять ядро без переработки проекта и легко добавлять новый функционал.

```
minetest-server/
├── mods/
│   ├── auth_laravel/          # Авторизация через Laravel API
│   │   ├── init.lua           # Основная логика авторизации
│   │   └── mod.conf           # Метаданные мода
│   └── vip_system/            # VIP-статусы и привилегии
│       ├── init.lua           # Логика VIP-системы
│       └── mod.conf           # Метаданные мода
├── config/
│   └── minetest.conf          # Конфигурация сервера
├── docs/
│   └── api.md                 # Спецификация Laravel API
├── install.sh                 # Скрипт установки
├── .env.example               # Шаблон переменных окружения
├── .gitignore                 # Исключения для Git
└── README.md
```

## Требования к серверу

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| CPU | 2 ядра | 4 ядра |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 20 ГБ SSD | 40 ГБ SSD |
| ОС | Ubuntu 20.04 | Ubuntu 22.04 |
| Сеть | 100 Мбит | 1 Гбит |

**Одновременный онлайн без лагов:**
- 4 ядра / 8 ГБ → 50–80 игроков
- 8 ядер / 16 ГБ → 80–120 игроков
- Выше 120 → шардирование (отдельный этап)

## Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Studio-Ameteur/minetest-server
cd minetest-server

# 2. Запустить скрипт установки (требуются права root)
sudo bash install.sh

# 3. Заполнить настройки
nano /opt/minetest-server/.env
```

## Настройка .env

Скопируйте `.env.example` в `.env` и заполните реальными значениями:

```bash
cp .env.example .env
nano .env
```

| Параметр | Описание |
|----------|----------|
| `LARAVEL_API_URL` | Базовый URL вашего Laravel API |
| `LARAVEL_SERVER_TOKEN` | Серверный токен для идентификации |
| `SERVER_PORT` | Порт сервера (по умолчанию 30000) |

## Управление сервером

```bash
# Запуск
systemctl start minetest

# Остановка
systemctl stop minetest

# Перезагрузка
systemctl restart minetest

# Статус
systemctl status minetest

# Логи в реальном времени
journalctl -u minetest -f
```

## Моды

### auth_laravel
Авторизует игроков через Laravel API. Пока API не готов — работает в stub-режиме с тестовыми аккаунтами. Для переключения на реальный API установите `stub_mode = false` в `mods/auth_laravel/init.lua`.

### vip_system
Управляет статусами и привилегиями игроков. Статусы: `basic`, `vip`, `premium`, `admin`. Привилегии подтягиваются из Laravel при входе и обновляются каждые 5 минут.

**Команды в игре:**
```
/mystatus — показать текущий статус и привилегии
```

## Интеграция с Laravel

Подробная спецификация API: [docs/api.md](docs/api.md)

Минимально необходимые эндпоинты:
- `POST /api/auth/login` — авторизация игрока
- `GET /api/account/status` — статус и привилегии

## Этапы разработки

- [x] Этап 1 — MVP: сервер, авторизация, VIP-статусы
- [ ] Этап 2 — Браузерная версия (WebAssembly + WebSocket-прокси)
