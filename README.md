# minetest-server

Игровой сервер на базе [Minetest](https://github.com/minetest/minetest) с интеграцией Laravel API.

## Описание

Форк Minetest с кастомной авторизацией через Laravel, системой VIP-статусов и привилегий.

## Структура проекта

```
minetest-server/
├── mods/
│   └── auth_laravel/      # Мод авторизации через Laravel API
├── config/
│   └── minetest.conf      # Конфигурация сервера
├── docs/
│   └── api.md             # Спецификация Laravel API
└── README.md
```

## Требования

- Ubuntu 20.04 / 22.04
- CPU: 2+ ядра
- RAM: 4+ ГБ
- SSD: 20+ ГБ

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/Studio-Ameteur/minetest-server
cd minetest-server

# Установить зависимости
sudo apt install minetest -y
```

## Запуск сервера

```bash
minetest --server --config config/minetest.conf
```

## Интеграция с Laravel

Сервер авторизует игроков через Laravel API. Подробнее: [docs/api.md](docs/api.md)

## Этапы разработки

- [x] Этап 1 — MVP: сервер, авторизация, VIP-статусы
- [ ] Этап 2 — Браузерная версия (WebAssembly)
