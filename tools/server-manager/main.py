# ===========================================
# ФАЙЛ: main.py
# Назначение: GUI управления сервером Minetest
# ===========================================

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import json
import os

from server import ServerConnection

# -------------------------------------------
# СЕССИЯ — запоминаем SSH-данные между запусками
# Хранится в %APPDATA%/minetest-manager/session.json (Windows)
# или ~/.config/minetest-manager/session.json (Linux/Mac)
# -------------------------------------------
def _session_path():
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    folder = os.path.join(base, "minetest-manager")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "session.json")

def load_session():
    try:
        with open(_session_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_session(data):
    try:
        with open(_session_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def clear_session():
    try:
        os.remove(_session_path())
    except Exception:
        pass

# -------------------------------------------
# ЦВЕТА И ШРИФТЫ
# -------------------------------------------
COLORS = {
    "bg":           "#1e1e2e",
    "bg_secondary": "#2a2a3e",
    "accent":       "#7c3aed",
    "accent_hover": "#6d28d9",
    "success":      "#22c55e",
    "danger":       "#ef4444",
    "warning":      "#f59e0b",
    "text":         "#e2e8f0",
    "text_muted":   "#94a3b8",
    "border":       "#3f3f5a",
}

FONTS = {
    "title":   ("Segoe UI", 16, "bold"),
    "heading": ("Segoe UI", 12, "bold"),
    "normal":  ("Segoe UI", 10),
    "small":   ("Segoe UI", 9),
    "mono":    ("Consolas", 9),
}

class FlatButton(tk.Button):
    def __init__(self, parent, text, command, color=None, **kwargs):
        color = color or COLORS["accent"]
        super().__init__(
            parent, text=text, command=command,
            bg=color, fg=COLORS["text"], font=FONTS["normal"],
            relief="flat", cursor="hand2", padx=16, pady=8, **kwargs
        )
        self._color = color
        self.bind("<Enter>", lambda e: self.config(bg=COLORS["accent_hover"]))
        self.bind("<Leave>", lambda e: self.config(bg=self._color))


# ===========================================
# ОКНО ВХОДА
# ===========================================
class LoginWindow:
    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.conn = ServerConnection()
        self._build()
        self._try_autologin()

    def _build(self):
        self.root.title("Minetest Manager — Вход")
        self.root.geometry("420x460")
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["bg"])
        self.root.eval("tk::PlaceWindow . center")

        tk.Label(self.root, text="⛏ Minetest Manager",
                 font=FONTS["title"], bg=COLORS["bg"],
                 fg=COLORS["text"]).pack(pady=(36, 4))

        tk.Label(self.root, text="Подключение к серверу по SSH",
                 font=FONTS["small"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(pady=(0, 24))

        frame = tk.Frame(self.root, bg=COLORS["bg"])
        frame.pack(padx=48, fill="x")

        session = load_session()
        self._field(frame, "IP-адрес сервера", "host_var", session.get("host", "93.189.228.62"))
        self._field(frame, "Логин", "user_var", session.get("user", "root"))
        self._field(frame, "Пароль", "pass_var", session.get("password", ""), show="*")

        # Галочка "запомнить"
        self.remember_var = tk.BooleanVar(value=bool(session.get("password")))
        chk_frame = tk.Frame(self.root, bg=COLORS["bg"])
        chk_frame.pack(pady=(12, 0))
        tk.Checkbutton(
            chk_frame, text="Запомнить данные входа",
            variable=self.remember_var,
            bg=COLORS["bg"], fg=COLORS["text_muted"],
            selectcolor=COLORS["bg_secondary"],
            activebackground=COLORS["bg"],
            font=FONTS["small"]
        ).pack()

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     font=FONTS["small"], bg=COLORS["bg"],
                                     fg=COLORS["text_muted"])
        self.status_label.pack(pady=(12, 0))

        self.btn = FlatButton(self.root, "Подключиться", self._connect)
        self.btn.pack(pady=(8, 0))

        tk.Label(self.root,
                 text="Пароль хранится локально, не передаётся третьим лицам",
                 font=FONTS["small"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(pady=(16, 0))

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
        tk.Entry(parent, **kwargs).pack(fill="x", ipady=8)
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x")

    def _try_autologin(self):
        """Если сессия сохранена — подключаемся автоматически"""
        session = load_session()
        if session.get("host") and session.get("user") and session.get("password"):
            self.status_var.set("Автоподключение...")
            self.status_label.config(fg=COLORS["text_muted"])
            self.btn.config(state="disabled")
            def do():
                ok, err = self.conn.connect(session["host"], session["user"], session["password"])
                if ok:
                    self.root.after(0, lambda: self.on_success(self.conn))
                else:
                    # Автовход не удался — показываем форму
                    clear_session()
                    self.root.after(0, lambda: (
                        self.status_var.set("Сессия устарела, войдите заново"),
                        self.status_label.config(fg=COLORS["warning"]),
                        self.btn.config(state="normal"),
                        self.pass_var.set("")
                    ))
            threading.Thread(target=do, daemon=True).start()

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
                if self.remember_var.get():
                    save_session({"host": host, "user": user, "password": password})
                else:
                    clear_session()
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
# ===========================================
class MainWindow:
    def __init__(self, root, conn):
        self.root = root
        self.conn = conn
        self.stats_window = None
        self.players_window = None
        self._build()
        self._refresh_status()

    def _build(self):
        self.root.title(f"Minetest Manager — {self.conn.host}")
        self.root.geometry("640x560")
        self.root.configure(bg=COLORS["bg"])
        self.root.eval("tk::PlaceWindow . center")

        # Шапка
        header = tk.Frame(self.root, bg=COLORS["bg_secondary"], pady=12)
        header.pack(fill="x")
        tk.Label(header, text="⛏ Minetest Manager",
                 font=FONTS["title"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text"]).pack(side="left", padx=20)

        # Кнопка выйти (сброс сессии)
        def logout():
            clear_session()
            self.conn.disconnect()
            for w in self.root.winfo_children():
                w.destroy()
            LoginWindow(self.root, lambda c: MainWindow(self.root, c))

        tk.Button(header, text="Выйти", command=logout,
                  bg=COLORS["bg_secondary"], fg=COLORS["text_muted"],
                  relief="flat", font=FONTS["small"], cursor="hand2").pack(side="right", padx=20)
        tk.Label(header, text=f"🖥 {self.conn.host}",
                 font=FONTS["small"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text_muted"]).pack(side="right", padx=8)

        # Статус
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

        # Управление сервером
        ctrl_frame = tk.LabelFrame(self.root, text=" Управление ",
                                   font=FONTS["small"], bg=COLORS["bg"],
                                   fg=COLORS["text_muted"], bd=1, relief="flat")
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

        # Управление игроками — новая панель
        players_frame = tk.LabelFrame(self.root, text=" Игроки ",
                                      font=FONTS["small"], bg=COLORS["bg"],
                                      fg=COLORS["text_muted"], bd=1, relief="flat")
        players_frame.pack(fill="x", padx=20, pady=(0, 12))
        p_row = tk.Frame(players_frame, bg=COLORS["bg"])
        p_row.pack(pady=12, padx=12)

        FlatButton(p_row, "👥  Управление игроками",
                   self._open_players,
                   color=COLORS["accent"]).pack(side="left", padx=6)

        # Стресс-тест
        stress_frame = tk.LabelFrame(self.root, text=" Нагрузочное тестирование ",
                                     font=FONTS["small"], bg=COLORS["bg"],
                                     fg=COLORS["text_muted"], bd=1, relief="flat")
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

        # Лог
        log_frame = tk.LabelFrame(self.root, text=" Лог действий ",
                                  font=FONTS["small"], bg=COLORS["bg"],
                                  fg=COLORS["text_muted"], bd=1, relief="flat")
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.log = scrolledtext.ScrolledText(log_frame, height=8,
                                             font=FONTS["mono"],
                                             bg=COLORS["bg_secondary"],
                                             fg=COLORS["text"],
                                             relief="flat", bd=0,
                                             state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self._log("Подключено к серверу: " + self.conn.host)

    def _server_action(self, action):
        funcs = {
            "start":   (self.conn.start_server,   "Запуск сервера..."),
            "stop":    (self.conn.stop_server,     "Остановка сервера..."),
            "restart": (self.conn.restart_server,  "Перезагрузка сервера..."),
        }
        func, msg = funcs[action]
        self._log(msg)
        def do():
            ok, detail = func()
            self.root.after(0, lambda: self._log("✓ Выполнено" if ok else f"✗ Ошибка: {detail}"))
            self.root.after(0, self._refresh_status)
        threading.Thread(target=do, daemon=True).start()

    def _refresh_status(self):
        def do():
            status = self.conn.get_service_status()
            labels = {
                "active":   ("● Работает",   COLORS["success"]),
                "inactive": ("● Остановлен", COLORS["danger"]),
                "failed":   ("● Ошибка",     COLORS["danger"]),
                "unknown":  ("● Неизвестно", COLORS["text_muted"]),
            }
            text, color = labels.get(status, labels["unknown"])
            self.root.after(0, lambda: (
                self.status_var.set(text),
                self.status_label.config(fg=color)
            ))
        threading.Thread(target=do, daemon=True).start()
        self.root.after(10000, self._refresh_status)

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

    def _open_stats(self):
        if self.stats_window and tk.Toplevel.winfo_exists(self.stats_window.window):
            self.stats_window.window.lift()
            return
        self.stats_window = StatsWindow(self.root, self.conn)

    def _open_players(self):
        if self.players_window and tk.Toplevel.winfo_exists(self.players_window.window):
            self.players_window.window.lift()
            return
        self.players_window = PlayersWindow(self.root, self.conn, self._log)

    def _log(self, message):
        ts = time.strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert("end", f"[{ts}] {message}\n")
        self.log.see("end")
        self.log.config(state="disabled")


# ===========================================
# ОКНО УПРАВЛЕНИЯ ИГРОКАМИ
# ===========================================
class PlayersWindow:
    def __init__(self, parent, conn, log_fn):
        self.conn = conn
        self.log = log_fn
        self.players = []
        self.filtered = []

        self.window = tk.Toplevel(parent)
        self.window.title("Управление игроками")
        self.window.geometry("620x520")
        self.window.configure(bg=COLORS["bg"])
        self.window.resizable(True, True)
        self._build()
        self._load_players()

    def _build(self):
        # Заголовок
        tk.Label(self.window, text="👥 Игроки сервера",
                 font=FONTS["title"], bg=COLORS["bg"],
                 fg=COLORS["text"]).pack(pady=(16, 8))

        # Поиск
        search_frame = tk.Frame(self.window, bg=COLORS["bg"])
        search_frame.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(search_frame, text="Поиск:", font=FONTS["small"],
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter())
        tk.Entry(search_frame, textvariable=self.search_var,
                 font=FONTS["normal"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text"], insertbackground=COLORS["text"],
                 relief="flat", bd=0).pack(side="left", fill="x", expand=True,
                                           padx=(8, 0), ipady=6)

        FlatButton(search_frame, "↺", self._load_players,
                   color=COLORS["bg_secondary"]).pack(side="left", padx=(8, 0))

        # Таблица игроков
        table_frame = tk.Frame(self.window, bg=COLORS["bg"])
        table_frame.pack(fill="both", expand=True, padx=20)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.Treeview",
                        background=COLORS["bg_secondary"],
                        foreground=COLORS["text"],
                        fieldbackground=COLORS["bg_secondary"],
                        rowheight=28,
                        font=FONTS["normal"])
        style.configure("Dark.Treeview.Heading",
                        background=COLORS["bg"],
                        foreground=COLORS["text_muted"],
                        font=FONTS["small"])
        style.map("Dark.Treeview", background=[("selected", COLORS["accent"])])

        cols = ("Ник", "Статус", "Привилегии")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                 style="Dark.Treeview", selectmode="browse")
        self.tree.heading("Ник", text="Ник")
        self.tree.heading("Статус", text="Статус")
        self.tree.heading("Привилегии", text="Привилегии")
        self.tree.column("Ник", width=140, anchor="w")
        self.tree.column("Статус", width=90, anchor="center")
        self.tree.column("Привилегии", width=340, anchor="w")

        scroll = ttk.Scrollbar(table_frame, orient="vertical",
                               command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Панель действий
        actions = tk.Frame(self.window, bg=COLORS["bg_secondary"], pady=12)
        actions.pack(fill="x")

        tk.Label(actions, text="Выбранный игрок:",
                 font=FONTS["small"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text_muted"]).pack(side="left", padx=(16, 4))

        self.selected_label = tk.Label(actions, text="—",
                                       font=FONTS["heading"],
                                       bg=COLORS["bg_secondary"],
                                       fg=COLORS["text"])
        self.selected_label.pack(side="left", padx=(0, 16))

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Статус
        tk.Label(actions, text="Статус:",
                 font=FONTS["small"], bg=COLORS["bg_secondary"],
                 fg=COLORS["text_muted"]).pack(side="left", padx=(0, 4))

        self.status_var = tk.StringVar(value="basic")
        status_cb = ttk.Combobox(actions, textvariable=self.status_var,
                                 values=["basic", "vip", "premium", "admin"],
                                 width=10, state="readonly", font=FONTS["normal"])
        status_cb.pack(side="left", padx=(0, 8))

        FlatButton(actions, "✓ Выдать статус",
                   self._apply_status,
                   color=COLORS["success"]).pack(side="left", padx=4)

        FlatButton(actions, "🔨 Забанить",
                   self._ban_player,
                   color=COLORS["danger"]).pack(side="left", padx=4)

        FlatButton(actions, "✓ Разбанить",
                   self._unban_player,
                   color=COLORS["warning"]).pack(side="left", padx=4)

        # Статус-строка
        self.info_var = tk.StringVar(value="Загрузка игроков...")
        tk.Label(self.window, textvariable=self.info_var,
                 font=FONTS["small"], bg=COLORS["bg"],
                 fg=COLORS["text_muted"]).pack(pady=6)

    def _load_players(self):
        self.info_var.set("Загрузка игроков с сервера...")
        def do():
            players = self.conn.get_players()
            self.window.after(0, lambda: self._populate(players))
        threading.Thread(target=do, daemon=True).start()

    def _populate(self, players):
        self.players = players
        self._filter()
        self.info_var.set(f"Игроков в базе: {len(players)}")

    def _filter(self):
        query = self.search_var.get().lower()
        self.filtered = [p for p in self.players
                         if query in p["name"].lower()] if query else list(self.players)
        self.tree.delete(*self.tree.get_children())
        for p in self.filtered:
            privs = ", ".join(p.get("privileges", []))
            self.tree.insert("", "end", iid=p["name"],
                             values=(p["name"], p.get("status", "?"), privs))

    def _on_select(self, _event):
        sel = self.tree.selection()
        if sel:
            self.selected_label.config(text=sel[0])
            # Подставляем текущий статус
            for p in self.filtered:
                if p["name"] == sel[0]:
                    self.status_var.set(p.get("status", "basic"))
                    break

    def _selected_name(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _apply_status(self):
        name = self._selected_name()
        if not name:
            messagebox.showwarning("Выберите игрока", "Сначала выберите игрока из списка.")
            return
        new_status = self.status_var.get()
        if not messagebox.askyesno("Подтверждение",
                f"Установить статус '{new_status}' игроку {name}?"):
            return
        self.info_var.set(f"Применяю статус {new_status} для {name}...")
        def do():
            ok, err = self.conn.set_player_status(name, new_status)
            msg = f"✓ Статус {new_status} выдан {name}" if ok else f"✗ Ошибка: {err}"
            self.log(msg)
            self.window.after(0, lambda: (self.info_var.set(msg), self._load_players()))
        threading.Thread(target=do, daemon=True).start()

    def _ban_player(self):
        name = self._selected_name()
        if not name:
            messagebox.showwarning("Выберите игрока", "Сначала выберите игрока из списка.")
            return
        if not messagebox.askyesno("Бан", f"Забанить игрока {name}?"):
            return
        def do():
            ok, _ = self.conn.ban_player(name)
            msg = f"🔨 Игрок {name} забанен" if ok else f"✗ Не удалось забанить {name}"
            self.log(msg)
            self.window.after(0, lambda: self.info_var.set(msg))
        threading.Thread(target=do, daemon=True).start()

    def _unban_player(self):
        name = self._selected_name()
        if not name:
            messagebox.showwarning("Выберите игрока", "Сначала выберите игрока из списка.")
            return
        def do():
            ok, _ = self.conn.unban_player(name)
            msg = f"✓ Игрок {name} разбанен" if ok else f"✗ Не удалось разбанить {name}"
            self.log(msg)
            self.window.after(0, lambda: self.info_var.set(msg))
        threading.Thread(target=do, daemon=True).start()


# ===========================================
# ОКНО СТАТИСТИКИ
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
        frame = tk.Frame(self.window, bg=COLORS["bg_secondary"], padx=24, pady=16)
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))
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
                     bg=COLORS["bg_secondary"], fg=COLORS["text"]).pack(side="left")
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
            var.set(f"{val}%" if key == "cpu" else str(val))


# ===========================================
# ТОЧКА ВХОДА
# ===========================================
def main():
    root = tk.Tk()
    root.configure(bg=COLORS["bg"])

    def on_login_success(conn):
        for widget in root.winfo_children():
            widget.destroy()
        MainWindow(root, conn)

    LoginWindow(root, on_login_success)
    root.mainloop()


if __name__ == "__main__":
    main()
