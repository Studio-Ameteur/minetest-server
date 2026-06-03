-- ===========================================
-- МОДУЛЬ: vip_system
-- Назначение: управление VIP-статусами и привилегиями
-- Синхронизация с Laravel API при входе игрока
-- Ядро Minetest не модифицируется
-- ===========================================

-- -------------------------------------------
-- НАСТРОЙКИ МОДУЛЯ
-- Измените под вашу систему статусов
-- -------------------------------------------
local SETTINGS = {
    -- Включить stub-режим (true = без реального API)
    stub_mode = true,

    -- Интервал проверки статуса в секундах (0 = только при входе)
    -- Например 300 = проверять каждые 5 минут пока игрок онлайн
    check_interval = 300,
}

-- -------------------------------------------
-- ТАБЛИЦА ПРИВИЛЕГИЙ ПО СТАТУСАМ
-- Измените список привилегий под вашу игру
-- Все доступные привилегии Minetest: interact, shout, fly, fast,
-- noclip, setspawn, ban, kick, home, teleport и другие
-- -------------------------------------------
local STATUS_PRIVILEGES = {
    -- Базовый аккаунт
    ["basic"] = {
        "interact",
        "shout",
    },

    -- VIP аккаунт
    ["vip"] = {
        "interact",
        "shout",
        "fly",
        "fast",
        "home",
    },

    -- Премиум аккаунт
    ["premium"] = {
        "interact",
        "shout",
        "fly",
        "fast",
        "home",
        "noclip",
        "teleport",
    },

    -- Администратор
    ["admin"] = {
        "interact",
        "shout",
        "fly",
        "fast",
        "home",
        "noclip",
        "teleport",
        "setspawn",
        "ban",
        "kick",
        "debug",
    },
}

-- -------------------------------------------
-- ПРИВЕТСТВЕННЫЕ СООБЩЕНИЯ ПО СТАТУСАМ
-- Измените текст под ваш проект
-- -------------------------------------------
local STATUS_MESSAGES = {
    ["basic"]   = "Добро пожаловать! Улучшите аккаунт на сайте для получения VIP.",
    ["vip"]     = "Добро пожаловать, VIP-игрок! Вам доступны полёт и ускорение.",
    ["premium"] = "Добро пожаловать, Premium-игрок! Все привилегии активны.",
    ["admin"]   = "Добро пожаловать, Администратор!",
}

-- -------------------------------------------
-- HTTP API
-- Используется для запросов к Laravel API
-- -------------------------------------------
local http = minetest.request_http_api()

-- -------------------------------------------
-- ХРАНИЛИЩЕ СЕССИЙ
-- Хранит статус игроков пока они онлайн
-- Очищается при выходе игрока
-- -------------------------------------------
local player_sessions = {}

-- -------------------------------------------
-- ПОЛУЧЕНИЕ СТАТУСА ЧЕРЕЗ LARAVEL API
-- Запрашивает текущий статус игрока
-- При stub_mode возвращает тестовые данные
-- -------------------------------------------
local function fetch_player_status(player_name, token, callback)
    -- Stub-режим для разработки
    if SETTINGS.stub_mode then
        local test_statuses = {
            ["admin"]      = "admin",
            ["vip_player"] = "vip",
            ["pro_player"] = "premium",
        }
        local status = test_statuses[player_name] or "basic"
        callback({ status = status, subscription_active = true })
        return
    end

    -- Реальный запрос к Laravel API
    http.fetch({
        url = minetest.settings:get("laravel_api_url") .. "/account/status",
        timeout = 5,
        method = "GET",
        extra_headers = {
            "Authorization: Bearer " .. token,
            "X-Server-Token: " .. minetest.settings:get("laravel_server_token"),
        },
    }, function(result)
        if not result.succeeded or result.code ~= 200 then
            minetest.log("error", "[vip_system] Ошибка получения статуса для " .. player_name)
            callback(nil)
            return
        end

        local data = minetest.parse_json(result.data)
        callback(data)
    end)
end

-- -------------------------------------------
-- ПРИМЕНЕНИЕ СТАТУСА И ПРИВИЛЕГИЙ
-- Выдаёт привилегии согласно статусу
-- Отправляет приветственное сообщение
-- -------------------------------------------
local function apply_status(player_name, status)
    -- Получаем список привилегий для статуса
    local privileges = STATUS_PRIVILEGES[status] or STATUS_PRIVILEGES["basic"]

    -- Сбрасываем старые привилегии и применяем новые
    local new_privs = {}
    for _, priv in ipairs(privileges) do
        new_privs[priv] = true
    end
    minetest.set_player_privs(player_name, new_privs)

    -- Сохраняем статус в сессии
    player_sessions[player_name] = {
        status = status,
        last_check = os.time(),
    }

    -- Отправляем приветственное сообщение
    local message = STATUS_MESSAGES[status] or STATUS_MESSAGES["basic"]
    minetest.chat_send_player(player_name, "[VIP] " .. message)

    minetest.log("action", "[vip_system] Статус применён для " .. player_name .. ": " .. status)
end

-- -------------------------------------------
-- ОБРАБОТЧИК ВХОДА ИГРОКА
-- Запрашивает статус и применяет привилегии
-- -------------------------------------------
minetest.register_on_joinplayer(function(player)
    local player_name = player:get_player_name()

    -- Получаем токен из сессии auth_laravel если он есть
    local token = player_sessions[player_name] and player_sessions[player_name].token or ""

    fetch_player_status(player_name, token, function(data)
        if not data then
            -- При ошибке применяем базовый статус
            apply_status(player_name, "basic")
            return
        end

        apply_status(player_name, data.status)
    end)
end)

-- -------------------------------------------
-- ПЕРИОДИЧЕСКАЯ ПРОВЕРКА СТАТУСА
-- Обновляет привилегии пока игрок онлайн
-- Интервал настраивается в SETTINGS.check_interval
-- Установите 0 чтобы отключить
-- -------------------------------------------
if SETTINGS.check_interval > 0 then
    minetest.register_globalstep(function(dtime)
        local now = os.time()
        for _, player in ipairs(minetest.get_connected_players()) do
            local player_name = player:get_player_name()
            local session = player_sessions[player_name]

            -- Проверяем если прошёл интервал
            if session and (now - session.last_check) >= SETTINGS.check_interval then
                fetch_player_status(player_name, "", function(data)
                    if data and data.status ~= session.status then
                        -- Статус изменился — обновляем привилегии
                        minetest.log("action", "[vip_system] Статус обновлён для " .. player_name ..
                            ": " .. session.status .. " → " .. data.status)
                        apply_status(player_name, data.status)
                    else
                        -- Статус не изменился — обновляем только время проверки
                        session.last_check = now
                    end
                end)
            end
        end
    end)
end

-- -------------------------------------------
-- ОБРАБОТЧИК ВЫХОДА ИГРОКА
-- Очищает сессию при выходе
-- -------------------------------------------
minetest.register_on_leaveplayer(function(player)
    local player_name = player:get_player_name()
    player_sessions[player_name] = nil
    minetest.log("action", "[vip_system] Сессия очищена для " .. player_name)
end)

-- -------------------------------------------
-- ЧАТОВАЯ КОМАНДА /mystatus
-- Игрок может проверить свой текущий статус
-- -------------------------------------------
minetest.register_chatcommand("mystatus", {
    description = "Показать ваш текущий статус и привилегии",
    func = function(player_name)
        local session = player_sessions[player_name]
        if not session then
            return true, "Статус не определён. Попробуйте переподключиться."
        end

        local privs = minetest.get_player_privs(player_name)
        local priv_list = {}
        for priv, _ in pairs(privs) do
            table.insert(priv_list, priv)
        end

        return true, "Ваш статус: " .. session.status ..
            "\nПривилегии: " .. table.concat(priv_list, ", ")
    end,
})

minetest.log("action", "[vip_system] Модуль загружен. Stub-режим: " .. tostring(SETTINGS.stub_mode))
