# Спецификация Laravel API

Документация по эндпоинтам Laravel API для интеграции с игровым сервером Minetest.

## Базовый URL

```
https://your-domain.com/api
```

## Авторизация запросов

Все запросы от игрового сервера к Laravel API должны содержать заголовок:

```
X-Server-Token: <серверный токен>
```

Токен задаётся в `config/minetest.conf` и на стороне Laravel.

---

## Эндпоинты

### 1. Авторизация игрока

**POST** `/api/auth/login`

Вызывается при входе игрока на сервер.

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

Вызывается после успешной авторизации для получения привилегий игрока.

**Заголовки:**
```
Authorization: Bearer <token>
```

**Успешный ответ** `200 OK`:
```json
{
  "user_id": 42,
  "username": "PlayerName",
  "status": "vip",
  "privileges": ["fly", "fast", "home", "setspawn"],
  "subscription_active": true,
  "subscription_expires": "2025-12-31"
}
```

**Возможные значения `status`:**
| Значение | Описание |
|----------|----------|
| `basic` | Базовый аккаунт |
| `vip` | VIP-подписка |
| `premium` | Премиум-подписка |
| `admin` | Администратор |

---

### 3. Проверка токена

**POST** `/api/auth/verify`

Проверка актуальности токена сессии.

**Тело запроса:**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Ответ** `200 OK`:
```json
{
  "valid": true,
  "user_id": 42
}
```

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `200` | Успешно |
| `401` | Не авторизован |
| `403` | Доступ запрещён |
| `404` | Пользователь не найден |
| `500` | Ошибка сервера |

---

## Примечание

До готовности Laravel API используется stub-модуль (`mods/auth_laravel/stub.lua`), который имитирует ответы API локально.
