# ===========================================
# ФАЙЛ: main.py
# Назначение: GUI управления сервером Minetest
# Запуск: python main.py
# Сборка exe: pyinstaller --onefile --windowed main.py
# ===========================================

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from server import ServerConnection

# -------------------------------------------
# НАСТРОЙКИ ИНТЕРФЕЙСА
# Цвета и шрифты — меняйте под свой вкус
# -------------------------------------------
COLORS = {
    "bg":           "#1e1e2e",   # Основной фон
    "bg_secondary": "#2a2a3e",   # Фон панелей
    "accent":       "#7c3aed",   # Фиолетовый акцент
    "accent_hover": "#6d28d9",   # Акцент при наведении
    "success":      "#22c55e",   # Зелёный — сервер работает
    "danger":       "#ef4444",   # Красный — ошибка/стоп
    "warning":      "#f59e0b",   # Жёлтый — предупреждение
    "text":         "#e2e8f0",   # Основной текст
    "text_muted":   "#94a3b8",   # Приглушённый текст
    "border":       "#3f3f5a",   # Цвет границ
}

FONTS = {
    "title":   ("Segoe UI", 16, "bold"),
    "heading": ("Segoe UI", 12, "bold"),
    "normal":  ("Segoe UI", 10),
    "small":   ("Segoe UI", 9),
    "mono":    ("Consolas", 9),
}

# -------------------------------------------
# ВСПОМОГАТЕЛЬНЫЙ КЛАСС КНОПКИ
# Кнопка с hover-эффектом
# -------------------------------------------
class FlatButton(tk.Button):
    def __init__(self, parent, text, command, color=None, **kwargs):
        color = color or COLORS["accent"]
        super().__init__(
            parent,
            text=text,
            command=command,
            bg=color,
            fg=COLORS["text"],
            font=FONTS["normal"],
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=8,
            **kwargs
        )
        self._color = color
        self.bind("<Enter>", lambda e: self.config(bg=COLORS["accent_hover"]))
        self.bind("<Leave>", lambda e: self.config(bg=self._color))


# ===========================================
# ОКНО ВХОДА
# Первое окно — ввод SSH данных
# ===========================================
class LoginWindow:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.conn = ServerConnection()
        self._build()

    def _build(self):
        self.root.title("Minetest Manager — Вход")
        self.root.geometry("420x420")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self.root.eval("tk::PlaceWindow . center")

        # Заголовок
        tk.Label(self.root, text="⛏ Minetest Manager",
                 font=FONTS["title"], bg=COLORS["bg"],
                 fg=COLORS["text"]).pack(pady=(36, 4))

        tk.Label(self.root, text="Подключение к серверу по SSH",
                 font=FONTS["small"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(pady=(0, 24))

        # Форма
        frame = tk.Frame(self.root, bg=COLORS["bg"])
        frame.pack(padx=48, fill="x")

        self._field(frame, "IP-адрес сервера", "host_var", "93.189.228.62")
        self._field(frame, "Логин", "user_var", "root")
        self._field(frame, "Пароль", "pass_var", "", show="*")

        # Статус подключения
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     font=FONTS["small"], bg=COLORS["bg"],
                                     fg=COLORS["text_muted"])
        self.status_label.pack(pady=(16, 0))

        # Кнопка входа
        self.btn = FlatButton(self.root, "Подключиться", self._connect)
        self.btn.pack(pady=(8, 0))

        # Инструкция
        tk.Label(self.root,
                 text="Данные хранятся только локально\nи не передаются третьим лицам",
                 font=FONTS["small"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(pady=(20, 0))

    def _field(self, parent, label, var_name, default="", show=None):
        tk.Label(parent, text=label, font=FONTS["small"],
                 bg=COLORS["bg"], fg=COLORS["text_muted"],
                 anchor="w").pack(fill="x", pady=(8, 2))

        var = tk.StringVar(value=default)
        setattr(self, var_name, var)

        kwargs = dict(textvariable=var, font=FONTS["normal"],
                      bg=COLORS["bg_secondary"], fg=COLORS["text"],
                      insertbackground=COLORS["text"],
                      relief="flat", bd=0)
        if show:
            kwargs["show"] = show

        entry = tk.Entry(parent, **kwargs)
        entry.pack(fill="x", ipady=8)

        # Подчёркивание вместо рамки
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x")

    def _connect(self):
        host = self.host_var.get().strip()
        user = self.user_var.get().strip()
        password = self.pass_var.get()

        if not host or not user or not password:
            self.status_var.set("Заполните все поля")
            self.status_label.config(fg=COLORS["danger"])
            return

        self.btn.config(state="disabled")
        self.status_var.set("Подключение...")
        self.status_label.config(fg=COLORS["text_muted"])
        self.root.update()

        def do_connect():
            ok, err = self.conn.connect(host, user, password)
            if ok:
                self.root.after(0, lambda: self.on_success(self.conn))
            else:
                self.root.after(0, lambda: self._on_error(err))

        threading.Thread(target=do_connect, daemon=True).start()

    def _on_error(self, err):
        self.status_var.set(err)
        self.status_label.config(fg=COLORS["danger"])
        self.btn.config(state="normal")


# ===========================================
# ГЛАВНОЕ ОКНО
# Управление сервером после входа
# ===========================================
class MainWindow:
    def __init__(self, root, conn):
        self.root = root
        self.conn = conn
        self.stats_window = None
        self._build()
        self._refresh_status()

    def _build(self):
        self.root.title(f"Minetest Manager — {self.conn.host}")
        self.root.geometry("600x520")
        self.root.configure(bg=COLORS["bg"])
        self.root.eval("tk::PlaceWindow . center")

        # Заголовок
        header = tk.Frame(self.root, bg=COLORS["bg_secondary"], pady=12)
        header.pack(fill="x")

        tk.Label(header, text="⛏ Minetest Manager",
                 font=FONTS["title"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text"]).pack(side="left", padx=20)

        tk.Label(header, text=f"🖥 {self.conn.host}",
                 font=FONTS["small"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text_muted"]).pack(side="right", padx=20)

        # Статус сервиса
        status_frame = tk.Frame(self.root, bg=COLORS["bg"], pady=16)
        status_frame.pack(fill="x", padx=20)

        tk.Label(status_frame, text="Статус сервера:",
                 font=FONTS["normal"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(side="left")

        self.status_var = tk.StringVar(value="Проверка...")
        self.status_label = tk.Label(status_frame, textvariable=self.status_var,
                                     font=FONTS["heading"], bg=COLORS["bg"],
                                     fg=COLORS["text_muted"])
        self.status_label.pack(side="left", padx=8)

        # Кнопки управления сервером
        ctrl_frame = tk.LabelFrame(self.root, text=" Управление ",
                                   font=FONTS["small"], bg=COLORS["bg"],
                                   fg=COLORS["text_muted"], bd=1,
                                   relief="flat")
        ctrl_frame.pack(fill="x", padx=20, pady=(0, 12))

        btn_row = tk.Frame(ctrl_frame, bg=COLORS["bg"])
        btn_row.pack(pady=12, padx=12)

        FlatButton(btn_row, "▶  Запустить",
                   lambda: self._server_action("start"),
                   color=COLORS["success"]).pack(side="left", padx=6)

        FlatButton(btn_row, "■  Остановить",
                   lambda: self._server_action("stop"),
                   color=COLORS["danger"]).pack(side="left", padx=6)

        FlatButton(btn_row, "↺  Перезагрузить",
                   lambda: self._server_action("restart"),
                   color=COLORS["warning"]).pack(side="left", padx=6)

        FlatButton(btn_row, "📊  Статистика",
                   self._open_stats).pack(side="left", padx=6)

        # Кнопка стресс-теста
        stress_frame = tk.LabelFrame(self.root, text=" Нагрузочное тестирование ",
                                     font=FONTS["small"], bg=COLORS["bg"],
                                     fg=COLORS["text_muted"], bd=1,
                                     relief="flat")
        stress_frame.pack(fill="x", padx=20, pady=(0, 12))

        stress_row = tk.Frame(stress_frame, bg=COLORS["bg"])
        stress_row.pack(pady=12, padx=12, fill="x")

        tk.Label(stress_row, text="Длительность (сек):",
                 font=FONTS["small"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(side="left")

        self.stress_duration = tk.IntVar(value=30)
        tk.Spinbox(stress_row, from_=10, to=300, increment=10,
                   textvariable=self.stress_duration, width=6,
                   bg=COLORS["bg_secondary"], fg=COLORS["text"],
                   relief="flat").pack(side="left", padx=8)

        FlatButton(stress_row, "⚡ Имитировать нагрузку",
                   self._run_stress,
                   color=COLORS["warning"]).pack(side="left", padx=8)

        # Лог действий
        log_frame = tk.LabelFrame(self.root, text=" Лог действий ",
                                  font=FONTS["small"], bg=COLORS["bg"],
                                  fg=COLORS["text_muted"], bd=1,
                                  relief="flat")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.log = scrolledtext.ScrolledText(log_frame, height=8,
                                             font=FONTS["mono"],
                                             bg=COLORS["bg_secondary"],
                                             fg=COLORS["text"],
                                             relief="flat", bd=0,
                                             state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)

        self._log("Подключено к серверу: " + self.conn.host)

    # -------------------------------------------
    # УПРАВЛЕНИЕ СЕРВЕРОМ
    # -------------------------------------------
    def _server_action(self, action):
        actions = {
            "start":   (self.conn.start_server,   "Запуск сервера..."),
            "stop":    (self.conn.stop_server,     "Остановка сервера..."),
            "restart": (self.conn.restart_server,  "Перезагрузка сервера..."),
        }
        func, msg = actions[action]
        self._log(msg)

        def do():
            ok = func()
            result = "✓ Выполнено" if ok else "✗ Ошибка выполнения"
            self.root.after(0, lambda: self._log(result))
            self.root.after(0, self._refresh_status)

        threading.Thread(target=do, daemon=True).start()

    # -------------------------------------------
    # ОБНОВЛЕНИЕ СТАТУСА СЕРВИСА
    # -------------------------------------------
    def _refresh_status(self):
        def do():
            status = self.conn.get_service_status()
            labels = {
                "active":   ("● Работает",    COLORS["success"]),
                "inactive": ("● Остановлен",  COLORS["danger"]),
                "failed":   ("● Ошибка",      COLORS["danger"]),
                "unknown":  ("● Неизвестно",  COLORS["text_muted"]),
            }
            text, color = labels.get(status, labels["unknown"])
            self.root.after(0, lambda: (
                self.status_var.set(text),
                self.status_label.config(fg=color)
            ))

        threading.Thread(target=do, daemon=True).start()
        # Обновляем каждые 10 секунд
        self.root.after(10000, self._refresh_status)

    # -------------------------------------------
    # СТРЕСС-ТЕСТ
    # -------------------------------------------
    def _run_stress(self):
        duration = self.stress_duration.get()
        if not messagebox.askyesno("Нагрузочный тест",
            f"Запустить стресс-тест на {duration} секунд?\n"
            "Сервер будет под максимальной нагрузкой."):
            return

        self._log(f"Запуск стресс-теста на {duration} сек...")

        def do():
            ok, msg = self.conn.run_stress_test(duration)
            self.root.after(0, lambda: self._log(("✓ " if ok else "✗ ") + msg))

        threading.Thread(target=do, daemon=True).start()

    # -------------------------------------------
    # ОТКРЫТИЕ ОКНА СТАТИСТИКИ
    # -------------------------------------------
    def _open_stats(self):
        if self.stats_window and tk.Toplevel.winfo_exists(self.stats_window.window):
            self.stats_window.window.lift()
            return
        self.stats_window = StatsWindow(self.root, self.conn)

    # -------------------------------------------
    # ЛОГ ДЕЙСТВИЙ
    # -------------------------------------------
    def _log(self, message):
        ts = time.strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert("end", f"[{ts}] {message}\n")
        self.log.see("end")
        self.log.config(state="disabled")


# ===========================================
# ОКНО СТАТИСТИКИ
# Открывается отдельным окном
# ===========================================
class StatsWindow:
    def __init__(self, parent, conn):
        self.conn = conn
        self.window = tk.Toplevel(parent)
        self.window.title("Статистика сервера")
        self.window.geometry("480x400")
        self.window.configure(bg=COLORS["bg"])
        self.window.resizable(False, False)
        self._build()
        self._refresh()

    def _build(self):
        tk.Label(self.window, text="📊 Статистика сервера",
                 font=FONTS["title"], bg=COLORS["bg"],
                 fg=COLORS["text"]).pack(pady=(20, 16))

        frame = tk.Frame(self.window, bg=COLORS["bg_secondary"],
                         padx=24, pady=16)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # Метрики
        self.metrics = {}
        rows = [
            ("cpu",      "🖥  CPU"),
            ("ram",      "💾  RAM (МБ)"),
            ("disk",     "💿  Диск"),
            ("uptime",   "⏱  Uptime"),
            ("players",  "👥  Игроков за час"),
            ("load_1m",  "📈  Нагрузка 1 мин"),
            ("load_5m",  "📈  Нагрузка 5 мин"),
            ("load_15m", "📈  Нагрузка 15 мин"),
        ]

        for key, label in rows:
            row = tk.Frame(frame, bg=COLORS["bg_secondary"])
            row.pack(fill="x", pady=4)

            tk.Label(row, text=label, font=FONTS["normal"],
                     bg=COLORS["bg_secondary"], fg=COLORS["text_muted"],
                     width=22, anchor="w").pack(side="left")

            var = tk.StringVar(value="—")
            self.metrics[key] = var

            tk.Label(row, textvariable=var, font=FONTS["heading"],
                     bg=COLORS["bg_secondary"],
                     fg=COLORS["text"]).pack(side="left")

        # Кнопка обновления
        FlatButton(self.window, "↺  Обновить", self._refresh).pack(pady=(0, 16))

    def _refresh(self):
        def do():
            stats = self.conn.get_stats()
            if stats:
                self.window.after(0, lambda: self._update(stats))

        threading.Thread(target=do, daemon=True).start()

    def _update(self, stats):
        for key, var in self.metrics.items():
            val = stats.get(key, "—")
            if key == "cpu":
                var.set(f"{val}%")
            else:
                var.set(str(val))


# ===========================================
# ТОЧКА ВХОДА
# ===========================================
def main():
    root = tk.Tk()
    root.configure(bg=COLORS["bg"])

    def on_login_success(conn):
        # Очищаем окно входа и открываем главное
        for widget in root.winfo_children():
            widget.destroy()
        MainWindow(root, conn)

    LoginWindow(root, on_login_success)
    root.mainloop()


if __name__ == "__main__":
    main()
