-- ===========================================
-- МОДУЛЬ: auth_laravel
-- Назначение: получение статуса игрока из Laravel API
-- Авторизация происходит стандартным механизмом Minetest
-- Laravel используется только для получения статуса и привилегий
-- ===========================================

-- -------------------------------------------
-- НАСТРОЙКИ МОДУЛЯ
-- -------------------------------------------
local SETTINGS = {
    api_url      = minetest.settings:get("laravel_api_url") or "http://localhost/api",
    server_token = minetest.settings:get("laravel_server_token") or "minetest-secret-token-2024",
    request_timeout = 5,
    stub_mode    = false,
}

-- -------------------------------------------
-- HTTP API
-- -------------------------------------------
local http = minetest.request_http_api()

-- -------------------------------------------
-- STUB-РЕЖИМ (заглушка для разработки)
-- Установите stub_mode = true чтобы включить
-- -------------------------------------------
local function stub_get_status(username)
    local test_accounts = {
        ["admin"]      = { status = "admin",   privileges = {"fly","fast","noclip","setspawn","ban","kick","debug","interact","shout","home","teleport"} },
        ["vip_player"] = { status = "vip",     privileges = {"fly","fast","home","interact","shout"} },
        ["pro_player"] = { status = "premium", privileges = {"fly","fast","home","noclip","teleport","interact","shout"} },
    }
    return test_accounts[username] or { status = "basic", privileges = {"interact","shout"} }
end

-- -------------------------------------------
-- ПОЛУЧЕНИЕ СТАТУСА ЧЕРЕЗ LARAVEL API
-- GET /api/player/status?username=PlayerName
-- -------------------------------------------
local function get_player_status(username, callback)
    if SETTINGS.stub_mode then
        minetest.log("action", "[auth_laravel] STUB: статус для " .. username)
        callback(stub_get_status(username))
        return
    end

    if not http then
        minetest.log("error", "[auth_laravel] HTTP API недоступен — проверьте secure.http_mods в minetest.conf")
        callback(stub_get_status(username))
        return
    end

    http.fetch({
     url     = SETTINGS.api_url .. "/player/status?username=" .. core.urlencode(username),
        timeout = SETTINGS.request_timeout,
        method  = "GET",
        extra_headers = {
            "X-Server-Token: " .. SETTINGS.server_token,
        },
    }, function(result)
        if not result.succeeded or result.code ~= 200 then
            minetest.log("warning", "[auth_laravel] API недоступен (код " .. tostring(result.code) .. "), применяем базовый статус для " .. username)
            callback({ status = "basic", privileges = {"interact","shout"} })
            return
        end

        local data = minetest.parse_json(result.data)
        if not data then
            minetest.log("error", "[auth_laravel] Ошибка парсинга ответа для " .. username)
            callback({ status = "basic", privileges = {"interact","shout"} })
            return
        end

        minetest.log("action", "[auth_laravel] Статус получен для " .. username .. ": " .. (data.status or "basic"))
        callback(data)
    end)
end

-- -------------------------------------------
-- ПРИМЕНЕНИЕ ПРИВИЛЕГИЙ
-- -------------------------------------------
local function apply_privileges(player_name, privileges)
    local new_privs = {}
    for _, priv in ipairs(privileges) do
        new_privs[priv] = true
    end
    minetest.set_player_privs(player_name, new_privs)
    minetest.log("action", "[auth_laravel] Привилегии применены для " .. player_name)
end

-- -------------------------------------------
-- ОБРАБОТЧИК ВХОДА ИГРОКА
-- Стандартная авторизация Minetest уже прошла
-- Здесь только получаем статус из Laravel
-- -------------------------------------------
minetest.register_on_joinplayer(function(player)
    local player_name = player:get_player_name()
    minetest.log("action", "[auth_laravel] Игрок вошёл: " .. player_name)

    get_player_status(player_name, function(data)
        if not data then
            minetest.chat_send_player(player_name, "Добро пожаловать! Статус: basic")
            return
        end

        apply_privileges(player_name, data.privileges or {"interact","shout"})
        minetest.chat_send_player(player_name, "Добро пожаловать! Ваш статус: " .. (data.status or "basic"))
    end)
end)

-- -------------------------------------------
-- ОБРАБОТЧИК ВЫХОДА
-- -------------------------------------------
minetest.register_on_leaveplayer(function(player)
    minetest.log("action", "[auth_laravel] Игрок вышел: " .. player:get_player_name())
end)

-- -------------------------------------------
-- КОМАНДА /mystatus
-- -------------------------------------------
minetest.register_chatcommand("mystatus", {
    description = "Показать ваш текущий статус",
    func = function(player_name)
        local privs = minetest.get_player_privs(player_name)
        local priv_list = {}
        for priv, _ in pairs(privs) do
            table.insert(priv_list, priv)
        end
        return true, "Привилегии: " .. table.concat(priv_list, ", ")
    end,
})

minetest.log("action", "[auth_laravel] Модуль загружен. Stub-режим: " .. tostring(SETTINGS.stub_mode))
