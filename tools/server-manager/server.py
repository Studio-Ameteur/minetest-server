# ===========================================
# МОДУЛЬ: server.py
# Назначение: подключение к серверу по SSH,
# управление сервисом Minetest, сбор статистики
# Используется main.py для всех операций с сервером
# ===========================================

import paramiko

# -------------------------------------------
# НАСТРОЙКИ
# Измените порт и имя сервиса если нужно
# -------------------------------------------
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

    # -------------------------------------------
    # ПОДКЛЮЧЕНИЕ ПО SSH
    # Возвращает (True, None) при успехе
    # Возвращает (False, текст_ошибки) при ошибке
    # -------------------------------------------
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

    # -------------------------------------------
    # ОТКЛЮЧЕНИЕ
    # -------------------------------------------
    def disconnect(self):
        if self.client:
            self.client.close()
        self.connected = False
        self.host = None

    # -------------------------------------------
    # ВЫПОЛНЕНИЕ КОМАНДЫ
    # Возвращает (stdout, stderr)
    # -------------------------------------------
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

    # -------------------------------------------
    # УПРАВЛЕНИЕ СЕРВИСОМ
    # Все методы возвращают (True, None) или (False, текст_ошибки)
    # -------------------------------------------
    def start_server(self):
        out, err = self.run_command(f"sudo systemctl start {SETTINGS['service_name']} 2>&1 && echo OK")
        if "OK" in out:
            return True, None
        return False, err or out or "Неизвестная ошибка"

    def stop_server(self):
        out, err = self.run_command(f"sudo systemctl stop {SETTINGS['service_name']} 2>&1 && echo OK")
        if "OK" in out:
            return True, None
        return False, err or out or "Неизвестная ошибка"

    def restart_server(self):
        out, err = self.run_command(f"sudo systemctl restart {SETTINGS['service_name']} 2>&1 && echo OK")
        if "OK" in out:
            return True, None
        return False, err or out or "Неизвестная ошибка"

    # -------------------------------------------
    # СТАТУС СЕРВИСА
    # Возвращает: "active", "inactive", "failed", "unknown"
    # -------------------------------------------
    def get_service_status(self):
        out, _ = self.run_command(f"systemctl is-active {SETTINGS['service_name']}")
        if out in ["active", "inactive", "failed"]:
            return out
        return "unknown"

    # -------------------------------------------
    # СТАТИСТИКА СЕРВЕРА
    # -------------------------------------------
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

    # -------------------------------------------
    # СТРЕСС-ТЕСТ
    # Возвращает (True, сообщение) или (False, ошибка)
    # -------------------------------------------
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

    # -------------------------------------------
    # ЛОГИ СЕРВЕРА
    # -------------------------------------------
    def get_logs(self, lines=50):
        out, _ = self.run_command(
            f"journalctl -u {SETTINGS['service_name']} -n {lines} --no-pager"
        )
        return out if out else "Логи недоступны"
