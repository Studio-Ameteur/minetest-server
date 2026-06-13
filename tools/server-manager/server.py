# ===========================================
# МОДУЛЬ: server.py
# ===========================================

import paramiko

SETTINGS = {
    "ssh_port":     22,
    "service_name": "minetest",
    "timeout":      10,
}

class ServerConnection:

    def __init__(self):
        self.client = None
        self.host = None
        self.connected = False

    def connect(self, host, username, password):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=host,
                port=SETTINGS["ssh_port"],
                username=username,
                password=password,
                timeout=SETTINGS["timeout"],
            )
            self.host = host
            self.connected = True
            return True, None
        except paramiko.AuthenticationException:
            return False, "Неверный логин или пароль"
        except paramiko.ssh_exception.NoValidConnectionsError:
            return False, "Не удалось подключиться. Проверьте IP и порт."
        except TimeoutError:
            return False, "Превышено время ожидания подключения"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"

    def disconnect(self):
        if self.client:
            self.client.close()
        self.connected = False
        self.host = None

    def run_command(self, command):
        if not self.connected:
            return "", "Нет подключения"
        try:
            _, stdout, stderr = self.client.exec_command(command, timeout=15)
            out = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            return out, err
        except Exception as e:
            return "", str(e)

    def start_server(self):
        out, err = self.run_command(f"sudo systemctl start {SETTINGS['service_name']} 2>&1 && echo OK")
        return ("OK" in out, None if "OK" in out else (err or out or "Неизвестная ошибка"))

    def stop_server(self):
        out, err = self.run_command(f"sudo systemctl stop {SETTINGS['service_name']} 2>&1 && echo OK")
        return ("OK" in out, None if "OK" in out else (err or out or "Неизвестная ошибка"))

    def restart_server(self):
        out, err = self.run_command(f"sudo systemctl restart {SETTINGS['service_name']} 2>&1 && echo OK")
        return ("OK" in out, None if "OK" in out else (err or out or "Неизвестная ошибка"))

    def get_service_status(self):
        out, _ = self.run_command(f"systemctl is-active {SETTINGS['service_name']}")
        return out if out in ["active", "inactive", "failed"] else "unknown"

    def get_stats(self):
        if not self.connected:
            return None
        stats = {}
        out, _ = self.run_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        try:
            stats["cpu"] = float(out) if out else 0.0
        except ValueError:
            stats["cpu"] = 0.0
        out, _ = self.run_command("free -m | awk 'NR==2{printf \"%s/%s\", $3, $2}'")
        stats["ram"] = out if out else "N/A"
        out, _ = self.run_command("df -h / | awk 'NR==2{printf \"%s/%s (%s)\", $3, $2, $5}'")
        stats["disk"] = out if out else "N/A"
        out, _ = self.run_command("uptime -p")
        stats["uptime"] = out if out else "N/A"
        out, _ = self.run_command(
            f"journalctl -u {SETTINGS['service_name']} --since '1 hour ago' | grep -c 'joins game' || echo 0"
        )
        stats["players"] = int(out) if out and out.isdigit() else 0
        out, _ = self.run_command("cat /proc/loadavg | awk '{print $1, $2, $3}'")
        if out:
            parts = out.split()
            stats["load_1m"]  = parts[0] if len(parts) > 0 else "0"
            stats["load_5m"]  = parts[1] if len(parts) > 1 else "0"
            stats["load_15m"] = parts[2] if len(parts) > 2 else "0"
        else:
            stats["load_1m"] = stats["load_5m"] = stats["load_15m"] = "0"
        return stats

    def run_stress_test(self, duration=30):
        if not self.connected:
            return False, "Нет подключения к серверу"
        self.run_command("apt install -y stress 2>/dev/null")
        out, _ = self.run_command("nproc")
        cores = int(out) if out and out.isdigit() else 2
        self.run_command(
            f"nohup stress --cpu {cores} --vm 1 --vm-bytes 512M "
            f"--timeout {duration}s > /tmp/stress.log 2>&1 &"
        )
        return True, f"Стресс-тест запущен на {cores} ядрах, {duration} сек."

    def get_logs(self, lines=50):
        out, _ = self.run_command(
            f"journalctl -u {SETTINGS['service_name']} -n {lines} --no-pager"
        )
        return out if out else "Логи недоступны"

    # -------------------------------------------
    # УПРАВЛЕНИЕ ИГРОКАМИ (через mod_storage Minetest)
    # Читаем SQLite БД мода auth_laravel напрямую
    # -------------------------------------------
    def get_players(self):
        """
        Возвращает список игроков из mod_storage auth_laravel.
        Файл: /home/minetest/.minetest/worlds/world/mod_storage/auth_laravel
        Это SQLite база с таблицей `entries` (key TEXT, value TEXT).
        Ключи вида: player:<username>  →  JSON со статусом
        """
        cmd = (
            "python3 -c \""
            "import sqlite3, json, os;"
            "db = '/home/minetest/.minetest/worlds/world/mod_storage/auth_laravel';"
            "conn = sqlite3.connect(db);"
            "rows = conn.execute(\\\"SELECT key, value FROM entries WHERE key LIKE 'player:%'\\\").fetchall();"
            "result = [];"
            "[result.append({'name': r[0][7:], **json.loads(r[1])}) for r in rows];"
            "print(json.dumps(result));"
            "conn.close()\""
        )
        out, err = self.run_command(cmd)
        if not out:
            return []
        try:
            import json
            players = json.loads(out)
            # убираем хэш пароля — незачем тянуть
            for p in players:
                p.pop("password_hash", None)
            return players
        except Exception:
            return []

    def set_player_status(self, username, new_status):
        """
        Меняет статус и привилегии игрока в mod_storage.
        """
        STATUS_PRIVS = {
            "basic":   ["interact", "shout"],
            "vip":     ["interact", "shout", "fly", "fast", "home"],
            "premium": ["interact", "shout", "fly", "fast", "home", "noclip", "teleport"],
            "admin":   ["interact", "shout", "fly", "fast", "home", "noclip", "teleport", "setspawn", "ban", "kick"],
        }
        privs = STATUS_PRIVS.get(new_status, ["interact", "shout"])
        import json
        privs_json = json.dumps(privs)
        cmd = (
            f"python3 -c \""
            f"import sqlite3, json;"
            f"db = '/home/minetest/.minetest/worlds/world/mod_storage/auth_laravel';"
            f"conn = sqlite3.connect(db);"
            f"row = conn.execute(\\\"SELECT value FROM entries WHERE key='player:{username}'\\\").fetchone();"
            f"data = json.loads(row[0]) if row else {{}};"
            f"data['status'] = '{new_status}';"
            f"data['privileges'] = {privs_json};"
            f"conn.execute(\\\"INSERT OR REPLACE INTO entries (key, value) VALUES ('player:{username}', ?)\\\", (json.dumps(data),));"
            f"conn.commit(); conn.close(); print('OK')\""
        )
        out, err = self.run_command(cmd)
        return "OK" in out, err if "OK" not in out else None

    def ban_player(self, username):
        """Бан через minetest-cli или minetest.conf ban_list"""
        out, err = self.run_command(
            f"grep -q '^ban_list' /home/minetest/.minetest/worlds/world/world.mt && "
            f"sed -i 's/^ban_list = /ban_list = {username},/' /home/minetest/.minetest/worlds/world/world.mt || "
            f"echo 'ban_list = {username}' >> /home/minetest/.minetest/worlds/world/world.mt && echo OK"
        )
        return True, None

    def unban_player(self, username):
        out, err = self.run_command(
            f"sed -i 's/{username},//g; s/,{username}//g' "
            f"/home/minetest/.minetest/worlds/world/world.mt && echo OK"
        )
        return True, None
