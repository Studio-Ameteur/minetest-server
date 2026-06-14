-- ===========================================
-- МОДУЛЬ: anticheat
-- Назначение: базовая защита сервера от читов
-- Покрывает:
--   1. Speed/Fly хаки (движение быстрее физически возможного)
--   2. X-Ray (анти-сканирование руды через блоки)
--   3. Спам в чате и командах
--   4. Дюп предметов (item duplication)
-- ===========================================

local SETTINGS = {
    -- Максимальная скорость игрока (узлов/сек) для проверки speed-хака.
    -- Базовая скорость ходьбы в Minetest ~4 узла/сек, бег ~5.6, спринт зависит от мода.
    -- Берём с запасом на лаги сети.
    max_speed_normal = 14,    -- м/с для игрока без fast
    max_speed_fast   = 25,    -- м/с для игрока с привилегией fast

    -- Порог "телепорта" — если игрок переместился дальше этого за один тик, считаем подозрительным
    teleport_threshold = 20,

    -- Сколько нарушений допускаем перед предупреждением/кик
    violations_warn = 5,
    violations_kick = 12,

    -- Антиспам чата
    chat_min_interval = 0.5,    -- секунд между сообщениями
    chat_max_repeats  = 4,      -- сколько одинаковых сообщений подряд допустимо

    -- Антиспам команд
    command_min_interval = 0.3,
}

-- -------------------------------------------
-- СОСТОЯНИЕ ИГРОКОВ (в памяти, не persist)
-- -------------------------------------------
local player_state = {}

local function get_state(name)
    if not player_state[name] then
        player_state[name] = {
            last_pos = nil,
            last_check = os.clock(),
            violations = 0,
            last_chat_time = 0,
            last_chat_msg = "",
            chat_repeat_count = 0,
            last_command_time = 0,
        }
    end
    return player_state[name]
end

-- -------------------------------------------
-- ЛОГИРОВАНИЕ НАРУШЕНИЙ
-- -------------------------------------------
local function log_violation(player_name, reason)
    minetest.log("warning", "[anticheat] " .. player_name .. ": " .. reason)

    local state = get_state(player_name)
    state.violations = state.violations + 1

    minetest.chat_send_player(player_name, "[Anticheat] Подозрительная активность: " .. reason)

    if state.violations >= SETTINGS.violations_kick then
        minetest.kick_player(player_name, "Заблокировано системой античита: " .. reason)
        minetest.log("action", "[anticheat] Игрок " .. player_name .. " кикнут за повторные нарушения")
        state.violations = 0
    elseif state.violations >= SETTINGS.violations_warn then
        -- Уведомляем всех админов онлайн
        for _, player in ipairs(minetest.get_connected_players()) do
            local pname = player:get_player_name()
            local privs = minetest.get_player_privs(pname)
            if privs.ban then
                minetest.chat_send_player(pname,
                    "[Anticheat] ВНИМАНИЕ: игрок " .. player_name ..
                    " набрал " .. state.violations .. " нарушений (" .. reason .. ")"
                )
            end
        end
    end
end

-- -------------------------------------------
-- 1. SPEED / FLY ХАКИ
-- Проверяем перемещение игрока каждую секунду.
-- Если скорость превышает физически возможную и у игрока нет
-- привилегии fast/fly — фиксируем нарушение.
-- -------------------------------------------
local function check_movement(player)
    local name = player:get_player_name()
    local state = get_state(name)
    local pos = player:get_pos()
    local privs = minetest.get_player_privs(name)

    if state.last_pos then
        local dt = os.clock() - state.last_check
        if dt > 0 then
            local dx = pos.x - state.last_pos.x
            local dy = pos.y - state.last_pos.y
            local dz = pos.z - state.last_pos.z
            local dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            local speed = dist / dt

            -- Игнорируем если игрок летит легитимно (privs.fly/noclip)
            if not privs.fly and not privs.noclip then
                local max_speed = privs.fast and SETTINGS.max_speed_fast or SETTINGS.max_speed_normal

                if dist > SETTINGS.teleport_threshold then
                    -- Резкий скачок позиции — похоже на телепорт-хак
                    log_violation(name, "резкое перемещение на " .. string.format("%.1f", dist) .. " блоков")
                elseif speed > max_speed then
                    log_violation(name, "движение со скоростью " .. string.format("%.1f", speed) .. " м/с (лимит " .. max_speed .. ")")
                end
            end

            -- Fly без привилегии: подъём в воздухе без опоры/жидкости/лестницы
            if not privs.fly and dy > 0.5 then
                local below = minetest.get_node({x = pos.x, y = pos.y - 1.5, z = pos.z})
                local node_def = minetest.registered_nodes[below.name]
                local is_climbable = node_def and node_def.climbable
                local is_liquid = node_def and node_def.liquidtype ~= "none"

                if not is_climbable and not is_liquid and below.name == "air" and dy > 1 then
                    log_violation(name, "подъём в воздухе без привилегии fly")
                end
            end
        end
    end

    state.last_pos = pos
    state.last_check = os.clock()
end

-- -------------------------------------------
-- 2. X-RAY ЗАЩИТА (базовая мера)
-- Полная защита от X-Ray требует контроля видимости карты на уровне
-- сервера, что ограничено в чистом Lua API. Базовая мера: детектим
-- аномально частые серии добычи ценных руд за короткий промежуток —
-- характерный признак X-Ray текстур.
-- -------------------------------------------
local VALUABLE_ORES = {
    ["default:stone_with_diamond"] = true,
    ["default:stone_with_gold"]    = true,
    ["default:stone_with_mese"]    = true,
    ["default:diamondblock"]       = true,
}

local ore_dig_log = {}

minetest.register_on_dignode(function(pos, oldnode, digger)
    if not digger then return end
    if not VALUABLE_ORES[oldnode.name] then return end

    local name = digger:get_player_name()
    ore_dig_log[name] = ore_dig_log[name] or {}
    local log = ore_dig_log[name]

    table.insert(log, os.clock())

    local now = os.clock()
    for i = #log, 1, -1 do
        if now - log[i] > 60 then
            table.remove(log, i)
        end
    end

    -- Если игрок выкопал больше 8 ценных руд за минуту — подозрительно
    if #log > 8 then
        log_violation(name, "аномально много ценных руд за минуту (" .. #log .. ") — возможен X-Ray")
        ore_dig_log[name] = {}
    end
end)

-- -------------------------------------------
-- 3. АНТИСПАМ ЧАТА И КОМАНД
-- -------------------------------------------
minetest.register_on_chat_message(function(player_name, message)
    local state = get_state(player_name)
    local now = os.clock()

    -- Слишком частые сообщения
    if now - state.last_chat_time < SETTINGS.chat_min_interval then
        minetest.chat_send_player(player_name, "[Anticheat] Не спамьте в чат, подождите немного.")
        return true -- блокируем сообщение
    end

    -- Повтор одного и того же сообщения
    if message == state.last_chat_msg then
        state.chat_repeat_count = state.chat_repeat_count + 1
        if state.chat_repeat_count >= SETTINGS.chat_max_repeats then
            minetest.chat_send_player(player_name, "[Anticheat] Сообщение повторяется слишком часто.")
            log_violation(player_name, "повторяющийся спам в чате")
            state.chat_repeat_count = 0
            return true
        end
    else
        state.chat_repeat_count = 0
    end

    state.last_chat_time = now
    state.last_chat_msg = message
    return false -- пропускаем сообщение дальше (другим модам/в чат)
end)

-- Антиспам команд (/команды)
minetest.register_on_chatcommand(function(name, command, params)
    local state = get_state(name)
    local now = os.clock()

    if now - state.last_command_time < SETTINGS.command_min_interval then
        return true -- блокируем слишком частый вызов команд
    end

    state.last_command_time = now
    return false
end)

-- -------------------------------------------
-- 4. ЗАЩИТА ОТ ДЮПА ПРЕДМЕТОВ
-- Основные векторы дюпа в Minetest:
--   - дюп через быстрые автоклик-макросы при работе с инвентарём/сундуками
--   - аномальная частота операций move/put/take
--
-- Базовая защита: ограничиваем частоту операций с инвентарём сверх
-- физически возможной (защита от дюп-макросов и автокликеров).
-- Детальная защита по конкретным контейнерам должна настраиваться
-- в модах нод (сундуки и т.п.) индивидуально.
-- -------------------------------------------
local inv_action_log = {}
local MAX_INV_ACTIONS_PER_SEC = 12 -- обычный игрок кликает значительно реже

minetest.register_on_player_inventory_action(function(player, action, inventory, inventory_info)
    local name = player:get_player_name()
    inv_action_log[name] = inv_action_log[name] or {count = 0, last_reset = os.clock()}
    local log = inv_action_log[name]

    local now = os.clock()
    if now - log.last_reset > 1 then
        log.count = 0
        log.last_reset = now
    end

    log.count = log.count + 1

    if log.count > MAX_INV_ACTIONS_PER_SEC then
        log_violation(name, "аномально частые действия с инвентарём (возможна дюп-макро)")
        log.count = 0
    end
end)

-- -------------------------------------------
-- ОСНОВНОЙ ЦИКЛ ПРОВЕРКИ ДВИЖЕНИЯ
-- Раз в секунду проверяем всех онлайн игроков
-- -------------------------------------------
local function movement_check_loop()
    for _, player in ipairs(minetest.get_connected_players()) do
        check_movement(player)
    end
    minetest.after(1, movement_check_loop)
end
minetest.after(1, movement_check_loop)

-- -------------------------------------------
-- ОЧИСТКА СОСТОЯНИЯ ПРИ ВЫХОДЕ ИГРОКА
-- -------------------------------------------
minetest.register_on_leaveplayer(function(player)
    local name = player:get_player_name()
    player_state[name] = nil
    ore_dig_log[name] = nil
    inv_action_log[name] = nil
end)

-- -------------------------------------------
-- КОМАНДА /anticheatstatus — статистика нарушений (для admin)
-- -------------------------------------------
minetest.register_chatcommand("anticheatstatus", {
    description = "Показать статистику нарушений античита (admin)",
    privs = { ban = true },
    func = function(caller, param)
        local lines = {"=== Anticheat: нарушения ==="}
        local any = false
        for name, state in pairs(player_state) do
            if state.violations > 0 then
                table.insert(lines, name .. ": " .. state.violations .. " нарушений")
                any = true
            end
        end
        if not any then
            table.insert(lines, "Нарушений не зафиксировано.")
        end
        return true, table.concat(lines, "\n")
    end,
})

minetest.log("action", "[anticheat] Модуль загружен")
