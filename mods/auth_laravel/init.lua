-- ===========================================
-- МОДУЛЬ: auth_laravel
-- Назначение: авторизация игроков через Laravel API
-- В stub-режиме: локальная БД с паролями и привилегиями
-- ===========================================

local SETTINGS = {
    api_url = minetest.settings:get("laravel_api_url") or "https://your-domain.com/api",
    server_token = minetest.settings:get("laravel_server_token") or "REPLACE_WITH_YOUR_TOKEN",
    request_timeout = 5,
    stub_mode = true,
}

-- -------------------------------------------
-- ЛОКАЛЬНОЕ ХРАНИЛИЩЕ (mod_storage)
-- Хранит: хэш пароля, статус, привилегии
-- Данные сохраняются между перезапусками сервера
-- -------------------------------------------
local storage = minetest.get_mod_storage()

-- Временное хранилище для игроков в процессе входа/регистрации
-- { [player_name] = { step = "password"|"confirm", password = "..." } }
local pending = {}

-- -------------------------------------------
-- ХЭШИРОВАНИЕ ПАРОЛЯ
-- Используем SHA1 через minetest.sha1()
-- Соль = имя игрока (защита от rainbow tables)
-- -------------------------------------------
local function hash_password(username, password)
    return minetest.sha1(username .. ":" .. password)
end

-- -------------------------------------------
-- РАБОТА С ЛОКАЛЬНОЙ БД
-- -------------------------------------------
local function db_get(username)
    local raw = storage:get_string("player:" .. username)
    if raw == "" then return nil end
    return minetest.parse_json(raw)
end

local function db_set(username, data)
    storage:set_string("player:" .. username, minetest.write_json(data))
end

-- -------------------------------------------
-- ПРИМЕНЕНИЕ ПРИВИЛЕГИЙ
-- -------------------------------------------
local STATUS_PRIVS = {
    basic   = {"interact", "shout"},
    vip     = {"interact", "shout", "fly", "fast", "home"},
    premium = {"interact", "shout", "fly", "fast", "home", "noclip", "teleport"},
    admin   = {"interact", "shout", "fly", "fast", "home", "noclip", "teleport", "setspawn", "ban", "kick"},
}

local function get_privs_for_status(status)
    return STATUS_PRIVS[status] or STATUS_PRIVS["basic"]
end

local function apply_privileges(player_name, privileges)
    local new_privs = {}
    for _, priv in ipairs(privileges) do
        new_privs[priv] = true
    end
    minetest.set_player_privs(player_name, new_privs)
    minetest.log("action", "[auth_laravel] Привилегии применены для " .. player_name)
end

-- -------------------------------------------
-- STUB: предустановленные аккаунты (только первый раз)
-- Если admin ещё не в БД — создаём с дефолтным паролем "admin123"
-- СМЕНИТЕ ПАРОЛЬ ПОСЛЕ ПЕРВОГО ВХОДА командой /setpassword
-- -------------------------------------------
local function ensure_default_accounts()
    if not db_get("admin") then
        db_set("admin", {
            password_hash = hash_password("admin", "admin123"),
            status = "admin",
            privileges = get_privs_for_status("admin"),
        })
        minetest.log("action", "[auth_laravel] Создан дефолтный аккаунт admin (пароль: admin123)")
    end
end

-- -------------------------------------------
-- РЕГИСТРАЦИЯ: шаг 1 — запрос пароля
-- -------------------------------------------
local function start_register(player_name)
    pending[player_name] = { step = "password" }
    minetest.chat_send_player(player_name,
        "=== РЕГИСТРАЦИЯ ===\nВы новый игрок. Введите пароль для вашего аккаунта:"
    )
    minetest.chat_send_player(player_name, "(Никто кроме вас не сможет войти с этим ником)")
end

-- -------------------------------------------
-- ВХОД: запрос пароля у существующего игрока
-- -------------------------------------------
local function start_login(player_name)
    pending[player_name] = { step = "login_password" }
    minetest.chat_send_player(player_name,
        "=== ВХОД ===\nВведите пароль для аккаунта '" .. player_name .. "':"
    )
end

-- -------------------------------------------
-- ОБРАБОТЧИК СООБЩЕНИЙ — перехватываем пароль
-- -------------------------------------------
minetest.register_on_chat_message(function(player_name, message)
    local state = pending[player_name]
    if not state then return false end -- не в процессе входа, пропускаем

    -- Скрываем сообщение от других игроков
    -- (возвращаем true = сообщение "съедено")

    if state.step == "password" then
        -- Регистрация: первый ввод пароля
        if #message < 4 then
            minetest.chat_send_player(player_name, "Пароль слишком короткий (минимум 4 символа). Попробуйте снова:")
            return true
        end
        state.password = message
        state.step = "confirm"
        minetest.chat_send_player(player_name, "Повторите пароль для подтверждения:")
        return true

    elseif state.step == "confirm" then
        -- Регистрация: подтверждение пароля
        if message ~= state.password then
            minetest.chat_send_player(player_name, "Пароли не совпадают. Введите пароль заново:")
            state.step = "password"
            state.password = nil
            return true
        end

        -- Сохраняем аккаунт
        local data = {
            password_hash = hash_password(player_name, message),
            status = "basic",
            privileges = get_privs_for_status("basic"),
        }
        db_set(player_name, data)
        pending[player_name] = nil

        apply_privileges(player_name, data.privileges)
        minetest.chat_send_player(player_name,
            "✓ Аккаунт создан! Ваш статус: basic\nДобро пожаловать, " .. player_name .. "!"
        )
        minetest.log("action", "[auth_laravel] Зарегистрирован новый игрок: " .. player_name)
        return true

    elseif state.step == "login_password" then
        -- Вход: проверяем пароль
        local data = db_get(player_name)
        if not data then
            -- Аккаунт исчез? Кикаем
            minetest.kick_player(player_name, "Ошибка: аккаунт не найден.")
            return true
        end

        if hash_password(player_name, message) ~= data.password_hash then
            minetest.chat_send_player(player_name, "Неверный пароль. Попробуйте снова:")
            return true
        end

        -- Пароль верный
        pending[player_name] = nil
        apply_privileges(player_name, data.privileges)
        minetest.chat_send_player(player_name,
            "✓ Вход выполнен! Ваш статус: " .. data.status .. "\nДобро пожаловать, " .. player_name .. "!"
        )
        minetest.log("action", "[auth_laravel] Игрок вошёл: " .. player_name .. " (статус: " .. data.status .. ")")
        return true
    end

    return false
end)

-- -------------------------------------------
-- ОБРАБОТЧИК ВХОДА ИГРОКА
-- -------------------------------------------
minetest.register_on_joinplayer(function(player)
    local player_name = player:get_player_name()
    minetest.log("action", "[auth_laravel] Игрок подключился: " .. player_name)

    -- Проверка временного бана (по нику, хранится в mod_storage)
    local data_check = db_get(player_name)
    if data_check and data_check.banned_until then
        local now = os.time()
        if data_check.banned_until > now then
            local remaining = data_check.banned_until - now
            local minutes = math.ceil(remaining / 60)
            minetest.kick_player(player_name,
                "Вы временно забанены. Осталось: " .. minutes .. " мин." ..
                (data_check.ban_reason and ("\nПричина: " .. data_check.ban_reason) or "")
            )
            minetest.log("action", "[auth_laravel] Кикнут (temp-ban): " .. player_name)
            return
        else
            -- Срок истёк — снимаем флаг
            data_check.banned_until = nil
            data_check.ban_reason = nil
            db_set(player_name, data_check)
        end
    end

    if SETTINGS.stub_mode then
        -- Блокируем все привилегии до авторизации
        minetest.set_player_privs(player_name, {})

        local data = db_get(player_name)
        if not data then
            -- Новый игрок — регистрация
            start_register(player_name)
        else
            -- Существующий игрок — требуем пароль
            start_login(player_name)
        end
        return
    end

    -- Реальный API режим (Laravel)
    -- TODO: реализовать когда API будет готов
end)

-- -------------------------------------------
-- ОБРАБОТЧИК ВЫХОДА ИГРОКА
-- -------------------------------------------
minetest.register_on_leaveplayer(function(player)
    local player_name = player:get_player_name()
    pending[player_name] = nil
    minetest.log("action", "[auth_laravel] Игрок отключился: " .. player_name)
end)

-- -------------------------------------------
-- КОМАНДА /setpassword — смена пароля
-- -------------------------------------------
minetest.register_chatcommand("setpassword", {
    params = "<новый_пароль>",
    description = "Сменить пароль аккаунта",
    func = function(player_name, param)
        if #param < 4 then
            return false, "Пароль слишком короткий (минимум 4 символа)."
        end
        local data = db_get(player_name)
        if not data then
            return false, "Аккаунт не найден."
        end
        data.password_hash = hash_password(player_name, param)
        db_set(player_name, data)
        return true, "Пароль успешно изменён."
    end,
})

-- -------------------------------------------
-- КОМАНДА /setstatus — выдать статус игроку (только admin)
-- -------------------------------------------
minetest.register_chatcommand("setstatus", {
    params = "<игрок> <basic|vip|premium|admin>",
    description = "Установить статус игроку (только для admin)",
    privs = { ban = true }, -- используем ban как маркер admin
    func = function(caller, param)
        local target, new_status = param:match("^(%S+)%s+(%S+)$")
        if not target or not new_status then
            return false, "Использование: /setstatus <игрок> <basic|vip|premium|admin>"
        end
        if not STATUS_PRIVS[new_status] then
            return false, "Неизвестный статус. Доступны: basic, vip, premium, admin"
        end

        local data = db_get(target)
        if not data then
            return false, "Игрок '" .. target .. "' не найден в БД."
        end

        data.status = new_status
        data.privileges = get_privs_for_status(new_status)
        db_set(target, data)

        -- Применяем немедленно если игрок онлайн
        local player = minetest.get_player_by_name(target)
        if player then
            apply_privileges(target, data.privileges)
            minetest.chat_send_player(target, "Ваш статус изменён на: " .. new_status)
        end

        return true, "Статус игрока " .. target .. " установлен на " .. new_status
    end,
})

-- -------------------------------------------
-- КОМАНДА /mystatus — посмотреть свой статус
-- -------------------------------------------
minetest.register_chatcommand("mystatus", {
    description = "Показать текущий статус и привилегии",
    func = function(player_name, _)
        local data = db_get(player_name)
        if not data then
            return false, "Аккаунт не найден."
        end
        local privs_str = table.concat(data.privileges, ", ")
        return true, "Статус: " .. data.status .. "\nПривилегии: " .. privs_str
    end,
})

-- -------------------------------------------
-- КОМАНДА /tempban — временный бан по нику (только admin)
-- Игрок кикается при следующей попытке входа на N минут.
-- -------------------------------------------
minetest.register_chatcommand("tempban", {
    params = "<игрок> <минуты> [причина]",
    description = "Временно забанить игрока по нику (только для admin)",
    privs = { ban = true },
    func = function(caller, param)
        local target, minutes_str, reason = param:match("^(%S+)%s+(%S+)%s*(.*)$")
        if not target or not minutes_str then
            return false, "Использование: /tempban <игрок> <минуты> [причина]"
        end

        local minutes = tonumber(minutes_str)
        if not minutes or minutes <= 0 then
            return false, "Минуты должны быть положительным числом."
        end

        local data = db_get(target)
        if not data then
            return false, "Игрок '" .. target .. "' не найден в БД."
        end

        data.banned_until = os.time() + (minutes * 60)
        data.ban_reason = (reason ~= "" and reason) or nil
        db_set(target, data)

        -- Если онлайн — кикаем сразу
        local player = minetest.get_player_by_name(target)
        if player then
            minetest.kick_player(target,
                "Вы временно забанены на " .. minutes .. " мин." ..
                (data.ban_reason and ("\nПричина: " .. data.ban_reason) or "")
            )
        end

        minetest.log("action", "[auth_laravel] " .. caller .. " выдал temp-ban игроку " .. target .. " на " .. minutes .. " мин.")
        return true, "Игрок " .. target .. " забанен на " .. minutes .. " минут."
    end,
})

-- -------------------------------------------
-- КОМАНДА /untempban — снять временный бан (только admin)
-- -------------------------------------------
minetest.register_chatcommand("untempban", {
    params = "<игрок>",
    description = "Снять временный бан по нику (только для admin)",
    privs = { ban = true },
    func = function(caller, target)
        if not target or target == "" then
            return false, "Использование: /untempban <игрок>"
        end

        local data = db_get(target)
        if not data then
            return false, "Игрок '" .. target .. "' не найден в БД."
        end

        if not data.banned_until then
            return true, "Игрок " .. target .. " не находится во временном бане."
        end

        data.banned_until = nil
        data.ban_reason = nil
        db_set(target, data)

        minetest.log("action", "[auth_laravel] " .. caller .. " снял temp-ban с игрока " .. target)
        return true, "Временный бан снят с игрока " .. target .. "."
    end,
})

-- Инициализация
ensure_default_accounts()
minetest.log("action", "[auth_laravel] Модуль загружен. Stub-режим: " .. tostring(SETTINGS.stub_mode))
