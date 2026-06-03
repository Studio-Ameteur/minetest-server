# Спецификация Laravel API

Документация по эндпоинтам Laravel API для интеграции с игровым сервером Minetest.

## Базовый URL

```
https://your-domain.com/api
```

## Авторизация запросов

Все запросы от игрового сервера содержат заголовок:

```
X-Server-Token: <серверный токен>
```

Токен задаётся в `config/minetest.conf` и `.env` на сервере, а также на стороне Laravel.

## Stub-режим

Пока Laravel API не готов — моды работают в stub-режиме. Переключение в `mods/auth_laravel/init.lua` и `mods/vip_system/init.lua`:

```lua
stub_mode = false  -- переключить на реальный API
```

---

## Эндпоинты

### 1. Авторизация игрока

**POST** `/api/auth/login`

Вызывается при входе игрока на сервер. Проверяет credentials и возвращает токен сессии.

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

---

### 2. Получение статуса аккаунта

**GET** `/api/account/status`

Вызывается после авторизации и каждые 5 минут пока игрок онлайн. Возвращает статус и список привилегий.

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
| Значение | Описание | Привилегии |
|----------|----------|-----------|
| `basic` | Базовый аккаунт | interact, shout |
| `vip` | VIP-подписка | + fly, fast, home |
| `premium` | Премиум-подписка | + noclip, teleport |
| `admin` | Администратор | все привилегии |

---

### 3. Проверка токена

**POST** `/api/auth/verify`

Проверяет актуальность токена сессии. Вызывается при переподключении игрока.

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
Игрок входит
    │
    ▼
auth_laravel → POST /api/auth/login
    │           (username + password)
    │
    ▼
Получаем token
    │
    ▼
vip_system → GET /api/account/status
    │          (Bearer token)
    │
    ▼
Применяем привилегии → игрок в игре
    │
    ▼
Каждые 5 минут → GET /api/account/status
    │              (обновление статуса)
    │
    ▼
Игрок выходит → сессия очищается
```

---

## Примечания для разработчика Laravel

- Серверный токен (`X-Server-Token`) валидируйте через middleware
- Токены игроков рекомендуется делать через Laravel Sanctum или JWT
- При смене статуса на сайте изменения применятся в игре в течение 5 минут (следующая проверка)
- Для мгновенного применения можно добавить эндпоинт принудительного обновления статуса
