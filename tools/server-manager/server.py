# ===========================================
# МОДУЛЬ: server.py
# Назначение: подключение к серверу по SSH,
# управление сервисом Minetest, сбор статистики
# Используется main.py для всех операций с сервером
# ===========================================

import paramiko
import time

# -------------------------------------------
# НАСТРОЙКИ
# Измените порт и имя сервиса если нужно
# -------------------------------------------
SETTINGS = {
    # Порт SSH (стандартный 22)
    "ssh_port": 22,

    # Имя systemd сервиса Minetest
    "service_name": "minetest",

    # Таймаут подключения в секундах
    "timeout": 10,
}

# -------------------------------------------
# КЛАСС ПОДКЛЮЧЕНИЯ К СЕРВЕРУ
# Все операции с сервером через этот класс
# -------------------------------------------
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
            # Автоматически принимаем ключ хоста
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
            return False, "Не удалось подключиться к серверу. Проверьте IP и порт."
        except TimeoutError:
            return False, "Превышено время ожидания подключения"
        except Exception as e:
            return False, f"Ошибка подключения: {str(e)}"

    # -------------------------------------------
    # ОТКЛЮЧЕНИЕ ОТ СЕРВЕРА
    # -------------------------------------------
    def disconnect(self):
        if self.client:
            self.client.close()
        self.connected = False
        self.host = None

    # -------------------------------------------
    # ВЫПОЛНЕНИЕ КОМАНДЫ НА СЕРВЕРЕ
    # Возвращает (stdout, stderr) или (None, текст_ошибки)
    # -------------------------------------------
    def run_command(self, command):
        if not self.connected:
            return None
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=15)
            out = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            # Если есть вывод — возвращаем его, иначе ошибку
            return out if out else (err or None)
        except Exception as e:
            return None

    # -------------------------------------------
    # УПРАВЛЕНИЕ СЕРВИСОМ MINETEST
    # Запуск, остановка, перезагрузка
    # sudo нужен если пользователь не root
    # -------------------------------------------
    def start_server(self):
        result = self.run_command(f"sudo systemctl start {SETTINGS['service_name']} 2>&1 && echo OK")
        return "OK" in (result or "")

    def stop_server(self):
        result = self.run_command(f"sudo systemctl stop {SETTINGS['service_name']} 2>&1 && echo OK")
        return "OK" in (result or "")

    def restart_server(self):
        result = self.run_command(f"sudo systemctl restart {SETTINGS['service_name']} 2>&1 && echo OK")
        return "OK" in (result or "")

    # -------------------------------------------
    # СТАТУС СЕРВИСА
    # Возвращает: "active", "inactive", "failed", "unknown"
    # -------------------------------------------
    def get_service_status(self):
        result = self.run_command(f"systemctl is-active {SETTINGS['service_name']}")
        if result in ["active", "inactive", "failed"]:
            return result
        return "unknown"

    # -------------------------------------------
    # СТАТИСТИКА СЕРВЕРА
    # Возвращает словарь с метриками системы
    # -------------------------------------------
    def get_stats(self):
        if not self.connected:
            return None

        stats = {}

        # Загрузка CPU в процентах
        cpu = self.run_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
        stats["cpu"] = float(cpu) if cpu else 0.0

        # Использование RAM
        ram = self.run_command("free -m | awk 'NR==2{printf \"%s/%s\", $3, $2}'")
        stats["ram"] = ram if ram else "N/A"

        # Использование диска
        disk = self.run_command("df -h / | awk 'NR==2{printf \"%s/%s (%s)\", $3, $2, $5}'")
        stats["disk"] = disk if disk else "N/A"

        # Uptime сервера
        uptime = self.run_command("uptime -p")
        stats["uptime"] = uptime if uptime else "N/A"

        # Количество онлайн игроков (парсим лог Minetest)
        players = self.run_command(
            f"journalctl -u {SETTINGS['service_name']} --since '1 hour ago' | "
            "grep -c 'joins game' || echo 0"
        )
        stats["players"] = int(players) if players and players.isdigit() else 0

        # Пиковая нагрузка (load average за 1/5/15 минут)
        load = self.run_command("cat /proc/loadavg | awk '{print $1, $2, $3}'")
        if load:
            parts = load.split()
            stats["load_1m"] = parts[0] if len(parts) > 0 else "0"
            stats["load_5m"] = parts[1] if len(parts) > 1 else "0"
            stats["load_15m"] = parts[2] if len(parts) > 2 else "0"
        else:
            stats["load_1m"] = stats["load_5m"] = stats["load_15m"] = "0"

        return stats

    # -------------------------------------------
    # ИМИТАЦИЯ МАКСИМАЛЬНОЙ НАГРУЗКИ
    # Запускает стресс-тест на сервере
    # Требует пакет: apt install stress
    # duration — длительность в секундах
    # -------------------------------------------
    def run_stress_test(self, duration=30):
        if not self.connected:
            return False, "Нет подключения к серверу"

        # Устанавливаем stress если нет
        self.run_command("apt install -y stress 2>/dev/null")

        # Определяем количество ядер
        cores = self.run_command("nproc")
        cores = int(cores) if cores and cores.isdigit() else 2

        # Запускаем стресс-тест в фоне
        self.run_command(
            f"nohup stress --cpu {cores} --vm 1 --vm-bytes 512M "
            f"--timeout {duration}s > /tmp/stress.log 2>&1 &"
        )

        return True, f"Стресс-тест запущен на {cores} ядрах, длительность {duration} сек."

    # -------------------------------------------
    # ПОЛУЧЕНИЕ ЛОГОВ СЕРВЕРА
    # Возвращает последние n строк логов
    # -------------------------------------------
    def get_logs(self, lines=50):
        result = self.run_command(
            f"journalctl -u {SETTINGS['service_name']} -n {lines} --no-pager"
        )
        return result if result else "Логи недоступны"
