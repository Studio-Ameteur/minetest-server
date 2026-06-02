-- ===========================================
-- МОДУЛЬ: auth_laravel
-- Назначение: авторизация игроков через Laravel API
-- Все запросы к API делаются через request_http_api()
-- Ядро Minetest не модифицируется
-- ===========================================

-- -------------------------------------------
-- НАСТРОЙКИ МОДУЛЯ
-- Измените значения под ваш Laravel API
-- -------------------------------------------
local SETTINGS = {
    -- Базовый URL вашего Laravel API
    api_url = minetest.settings:get("laravel_api_url") or "https://your-domain.com/api",

    -- Серверный токен для идентификации сервера на стороне Laravel
    server_token = minetest.settings:get("laravel_server_token") or "REPLACE_WITH_YOUR_TOKEN",

    -- Таймаут HTTP-запроса в секундах
    request_timeout = 5,

    -- Включить stub-режим (true = использовать заглушку вместо реального API)
    -- Установите false когда Laravel API будет готов
    stub_mode = true,
}

-- -------------------------------------------
-- HTTP API
-- Minetest предоставляет HTTP API только доверенным модам
-- Мод должен быть указан в secure.http_mods в minetest.conf
-- -------------------------------------------
local http = minetest.request_http_api()

-- -------------------------------------------
-- STUB-РЕЖИМ (заглушка для разработки)
-- Используется пока Laravel API не готов
-- Возвращает фиктивные данные для тестирования
-- Чтобы отключить — установите stub_mode = false в SETTINGS
-- -------------------------------------------
local function stub_get_account(username)
    -- Тестовые аккаунты для разработки
    -- Формат: [username] = { status, privileges }
    local test_accounts = {
        ["admin"] = {
            success = true,
            user_id = 1,
            status = "admin",
            privileges = {"fly", "fast", "noclip", "setspawn", "ban", "kick"},
            subscription_active = true,
        },
        ["vip_player"] = {
            success = true,
            user_id = 2,
            status = "vip",
            privileges = {"fly", "fast", "home"},
            subscription_active = true,
        },
    }

    -- Если игрок есть в тестовых аккаунтах — возвращаем его данные
    if test_accounts[username] then
        return test_accounts[username]
    end

    -- По умолчанию — базовый аккаунт
    return {
        success = true,
        user_id = 0,
        status = "basic",
        privileges = {"interact", "shout"},
        subscription_active = false,
    }
end

-- -------------------------------------------
-- ЗАПРОС К LARAVEL API
-- Отправляет GET-запрос к /api/account/status
-- Возвращает статус и привилегии игрока
-- -------------------------------------------
local function get_account_status(username, token, callback)
    -- Если включён stub-режим — возвращаем заглушку
    if SETTINGS.stub_mode then
        minetest.log("action", "[auth_laravel] STUB режим: получен статус для " .. username)
        callback(stub_get_account(username))
        return
    end

    -- Формируем запрос к Laravel API
    http.fetch({
        url = SETTINGS.api_url .. "/account/status",
        timeout = SETTINGS.request_timeout,
        method = "GET",
        extra_headers = {
            "Authorization: Bearer " .. token,
            "X-Server-Token: " .. SETTINGS.server_token,
            "Content-Type: application/json",
        },
    }, function(result)
        -- Проверяем успешность запроса
        if not result.succeeded or result.code ~= 200 then
            minetest.log("error", "[auth_laravel] Ошибка запроса статуса: код " .. tostring(result.code))
            callback(nil)
            return
        end

        -- Парсим JSON-ответ
        local data = minetest.parse_json(result.data)
        if not data then
            minetest.log("error", "[auth_laravel] Ошибка парсинга ответа API")
            callback(nil)
            return
        end

        callback(data)
    end)
end

-- -------------------------------------------
-- ЗАПРОС АВТОРИЗАЦИИ
-- Отправляет POST-запрос к /api/auth/login
-- Возвращает токен сессии при успехе
-- -------------------------------------------
local function auth_login(username, password, callback)
    -- Если включён stub-режим — пропускаем авторизацию
    if SETTINGS.stub_mode then
        minetest.log("action", "[auth_laravel] STUB режим: авторизация " .. username)
        callback({ success = true, token = "stub_token_" .. username })
        return
    end

    -- Формируем POST-запрос
    http.fetch({
        url = SETTINGS.api_url .. "/auth/login",
        timeout = SETTINGS.request_timeout,
        method = "POST",
        extra_headers = {
            "X-Server-Token: " .. SETTINGS.server_token,
            "Content-Type: application/json",
        },
        data = minetest.write_json({
            username = username,
            password = password,
        }),
    }, function(result)
        if not result.succeeded then
            minetest.log("error", "[auth_laravel] Ошибка подключения к API")
            callback(nil)
            return
        end

        local data = minetest.parse_json(result.data)
        if not data or not data.success then
            minetest.log("action", "[auth_laravel] Неверные credentials для " .. username)
            callback(nil)
            return
        end

        callback(data)
    end)
end

-- -------------------------------------------
-- ПРИМЕНЕНИЕ ПРИВИЛЕГИЙ
-- Выдаёт игроку привилегии согласно статусу из Laravel
-- Список привилегий настраивается на стороне Laravel API
-- -------------------------------------------
local function apply_privileges(player_name, privileges)
    -- Сбрасываем текущие привилегии
    local current = minetest.get_player_privs(player_name)
    for priv, _ in pairs(current) do
        current[priv] = nil
    end

    -- Применяем привилегии из API
    local new_privs = {}
    for _, priv in ipairs(privileges) do
        new_privs[priv] = true
    end

    minetest.set_player_privs(player_name, new_privs)
    minetest.log("action", "[auth_laravel] Привилегии применены для " .. player_name .. ": " .. table.concat(privileges, ", "))
end

-- -------------------------------------------
-- ОБРАБОТЧИК ВХОДА ИГРОКА
-- Вызывается автоматически при подключении игрока
-- Порядок: авторизация → получение статуса → применение привилегий
-- -------------------------------------------
minetest.register_on_joinplayer(function(player)
    local player_name = player:get_player_name()
    minetest.log("action", "[auth_laravel] Игрок подключился: " .. player_name)

    -- Шаг 1: авторизуем игрока
    -- В реальном режиме пароль приходит от клиента через SRP-протокол
    auth_login(player_name, "", function(auth_result)
        if not auth_result then
            -- Кикаем игрока если авторизация не удалась
            minetest.kick_player(player_name, "Ошибка авторизации. Попробуйте позже.")
            return
        end

        -- Шаг 2: получаем статус и привилегии
        get_account_status(player_name, auth_result.token, function(account)
            if not account then
                minetest.kick_player(player_name, "Не удалось получить данные аккаунта.")
                return
            end

            -- Шаг 3: применяем привилегии
            apply_privileges(player_name, account.privileges)

            -- Уведомляем игрока о статусе
            minetest.chat_send_player(player_name,
                "Добро пожаловать! Ваш статус: " .. account.status
            )

            minetest.log("action", "[auth_laravel] Статус игрока " .. player_name .. ": " .. account.status)
        end)
    end)
end)

-- -------------------------------------------
-- ОБРАБОТЧИК ВЫХОДА ИГРОКА
-- Сбрасывает привилегии при выходе
-- -------------------------------------------
minetest.register_on_leaveplayer(function(player)
    local player_name = player:get_player_name()
    minetest.log("action", "[auth_laravel] Игрок отключился: " .. player_name)
end)

minetest.log("action", "[auth_laravel] Модуль загружен. Stub-режим: " .. tostring(SETTINGS.stub_mode))
