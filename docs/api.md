# Спецификация Laravel API

Документация по эндпоинтам Laravel API для интеграции с игровым сервером Minetest.

## Текущий статус интеграции

| Эндпоинт | Статус |
|----------|--------|
| POST /api/auth/login | ⏳ Ожидаем реализацию |
| GET /api/account/status | ⏳ Ожидаем реализацию |
| POST /api/auth/verify | ⏳ Ожидаем реализацию |

Пока API не готов — сервер работает в **stub-режиме** (имитация ответов API).
Переключение: `stub_mode = false` в `mods/auth_laravel/init.lua` и `mods/vip_system/init.lua`.

---

## Базовый URL

```
https://your-domain.com/api
```

## Авторизация запросов

Все запросы от игрового сервера содержат заголовок:

```
X-Server-Token: <серверный токен>
```

Токен задаётся в `.env` на сервере (`LARAVEL_SERVER_TOKEN`) и валидируется на стороне Laravel через middleware.

---

## Эндпоинты

### 1. Авторизация игрока

**POST** `/api/auth/login`

Вызывается при каждом входе игрока на сервер.

**Заголовки:**
```
X-Server-Token: <серверный токен>
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "username": "PlayerName",
  "password": "hashed_password"
}
```

**Успешный ответ** `200 OK`:
```json
{
  "success": true,
  "user_id": 42,
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Ошибка** `401 Unauthorized`:
```json
{
  "success": false,
  "message": "Неверный логин или пароль"
}
```

> При ошибке авторизации игрок автоматически кикается с сервера.

---

### 2. Получение статуса аккаунта

**GET** `/api/account/status`

Вызывается после авторизации и каждые 5 минут пока игрок онлайн.
Возвращает статус и список привилегий которые будут применены в игре.

**Заголовки:**
```
Authorization: Bearer <token>
X-Server-Token: <серверный токен>
```

**Успешный ответ** `200 OK`:
```json
{
  "user_id": 42,
  "username": "PlayerName",
  "status": "vip",
  "privileges": ["interact", "shout", "fly", "fast", "home"],
  "subscription_active": true,
  "subscription_expires": "2025-12-31"
}
```

**Возможные значения `status`:**
| Значение | Описание | Привилегии в игре |
|----------|----------|------------------|
| `basic` | Базовый аккаунт | interact, shout |
| `vip` | VIP-подписка | + fly, fast, home |
| `premium` | Премиум-подписка | + noclip, teleport |
| `admin` | Администратор | все привилегии |

> Список привилегий в поле `privileges` применяется напрямую — можно гибко настраивать на стороне Laravel.

---

### 3. Проверка токена

**POST** `/api/auth/verify`

Проверяет актуальность токена сессии при переподключении игрока.

**Заголовки:**
```
X-Server-Token: <серверный токен>
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Успешный ответ** `200 OK`:
```json
{
  "valid": true,
  "user_id": 42,
  "username": "PlayerName"
}
```

**Истёкший токен** `401`:
```json
{
  "valid": false,
  "message": "Токен истёк"
}
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `200` | Успешно |
| `401` | Не авторизован / неверный токен |
| `403` | Доступ запрещён (неверный серверный токен) |
| `404` | Пользователь не найден |
| `500` | Внутренняя ошибка сервера |

---

## Схема взаимодействия

```
Игрок входит на сервер
        │
        ▼
auth_laravel → POST /api/auth/login
        │       (username + password)
        │
        ├── Ошибка → игрок кикается
        │
        ▼
Получаем token
        │
        ▼
vip_system → GET /api/account/status
        │     (Bearer token)
        │
        ▼
Применяем привилегии → игрок в игре
        │
        ▼
Каждые 5 минут → GET /api/account/status
        │          (обновление статуса)
        │
        ├── Статус изменился → обновляем привилегии
        │
        ▼
Игрок выходит → сессия очищается
```

---

## Примечания для разработчика Laravel

- `X-Server-Token` валидируйте через middleware на всех эндпоинтах
- Токены игроков рекомендуется реализовать через Laravel Sanctum или JWT
- При смене статуса на сайте изменения применятся в игре в течение 5 минут
- Для мгновенного применения можно добавить эндпоинт принудительного обновления
- Поле `privileges` можно формировать динамически — сервер применит список как есть

---

## Stub-режим (текущее состояние)

Пока API не готов сервер использует заглушку. Тестовые аккаунты:

| Логин | Статус | Привилегии |
|-------|--------|-----------|
| `admin` | admin | все привилегии |
| `vip_player` | vip | fly, fast, home + базовые |
| `pro_player` | premium | noclip, teleport + vip + базовые |
| Любой другой | basic | interact, shout |

Переключение на реальный API:
```lua
-- mods/auth_laravel/init.lua и mods/vip_system/init.lua
stub_mode = false  -- было true
```
