import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import json
import os
import sys

# ============================================================
#  Версия программы — ЕДИНСТВЕННОЕ место, где её менять.
#  При изменении APP_VERSION не забудьте пересобрать .exe
#  (см. build.bat — он сам обновит version_info.txt).
# ============================================================
APP_NAME    = "BundlePackerApp"
APP_TITLE   = "Сопоставление кодов маркировки"
APP_VERSION = "1.2.8"

FONT_UI_BOLD  = ("Segoe UI", 10, "bold")
FONT_MONO_BIG = ("Consolas", 12)
COLOR_PRIMARY     = "#004080"   # акцент (заголовок статуса)
COLOR_HINT        = "#667085"   # подсказки
COLOR_SUCCESS     = "#0a7d32"   # сохранено
COLOR_WARNING     = "#b54708"   # отмена

# Версия СХЕМЫ state.json — отдельно от версии программы.
# Поднимайте только при несовместимом изменении структуры JSON.
STATE_FORMAT_VERSION = 2

def get_state_file_path() -> str:
    """Путь к файлу состояния в профиле пользователя (%APPDATA%/BundlePackerApp/state.json)."""
    appdata = os.getenv("APPDATA")
    if not appdata:
        appdata = os.path.expanduser("~")
    app_dir = os.path.join(appdata, "BundlePackerApp")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, "state.json")


STATE_FILE = get_state_file_path()

class BundlePackerApp:
    #ITEMS_PER_SET = 3  # сколько товаров в наборе
    CODE_LENGTH = 31   # сколько первых символов сохраняем

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry("700x550")

        # --- Установка иконки окна ---
        # sys._MEIPASS существует только в собранном .exe
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_path, "icon.ico")
        try:
            self.root.iconbitmap(icon_path)
        except tk.TclError:
            # Если файла нет — просто пропускаем (не роняем программу)
            pass
        # ----------------------------

        # Данные: список кортежей (код_товара, код_набора)
        self.rows = []

        # Текущее состояние ввода
        self.current_set = None
        self.current_items = []
        self.set_counter = 0           # сколько наборов уже начато
        self.items_per_set = 3         # кол-во товаров в наборе (по умолчанию 3)
        self.check_duplicates = True   # настройка проверки дубликатов (по умолчанию включено)

        # --- Верхняя панель: статус и подсказка ---
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            root, textvariable=self.status_var,
            font=("Segoe UI", 12, "bold"), fg="#004080"
        )
        self.status_label.pack(pady=8)

        self.hint_var = tk.StringVar()
        self.hint_label = tk.Label(
            root, textvariable=self.hint_var,
            font=("Segoe UI", 10), fg="#555"
        )
        self.hint_label.pack(pady=2)

        # --- Поле ввода ---
        frame_input = tk.Frame(root)
        frame_input.pack(pady=10)

        tk.Label(frame_input, text="Товаров в наборе:", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self.items_var = tk.IntVar(value=self.items_per_set)
        self.items_spin = tk.Spinbox(
            frame_input, from_=1, to=100, width=4,
            textvariable=self.items_var,
            font=("Segoe UI", 11),
            command=self.on_items_changed,
        )
        self.items_spin.pack(side=tk.LEFT, padx=(0, 15))
        # при ручном вводе в Spinbox command не всегда срабатывает — ловим по фокусу/Enter
        self.items_spin.bind("<FocusOut>", lambda e: self.on_items_changed())
        self.items_spin.bind("<Return>",   lambda e: self.on_items_changed())

        tk.Label(frame_input, text="Сканируйте код:", font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=5)
        self.entry = tk.Entry(frame_input, font=("Consolas", 12), width=40)
        self.entry.pack(side=tk.LEFT, padx=5)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.focus_set()

        # --- Кнопки ---
        frame_btn = tk.Frame(root)
        frame_btn.pack(pady=10)

        tk.Button(frame_btn, text="Отменить последнее", width=20,
                  command=self.undo_last).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Сбросить всё", width=15,
                  command=self.reset_all).pack(side=tk.LEFT, padx=5)
        tk.Button(
            frame_btn,
            text="Завершить и показать таблицу",
            width=28,
            command=self.finish,
            bg=COLOR_PRIMARY,
            fg="white",
            activebackground="#0059b3",
            activeforeground="white",
            font=FONT_UI_BOLD,
            relief=tk.RAISED,
            bd=2,
            cursor="hand2",
        ).pack(side=tk.LEFT, padx=(20, 5))
        
#        tk.Button(frame_btn, text="О программе", width=15,
#                  command=self.show_about).pack(side=tk.LEFT, padx=5)
#
#        # --- Журнал ввода (что уже отсканировано) ---
#        tk.Label(root, text="Журнал ввода:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)
#        self.log = tk.Text(root, height=8, font=("Consolas", 10))
#        self.log.pack(fill=tk.X, padx=10, pady=5)
#        self.log.configure(state="disabled")

        # --- Журнал ввода (растягивается до низа окна) ---
        tk.Label(root, text="Журнал ввода:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", padx=10
        )

        log_frame = tk.Frame(root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.log = tk.Text(log_frame, height=1, font=("Consolas", 10))
        self.log.tag_configure("set",     foreground=COLOR_PRIMARY, font=FONT_MONO_BIG)
        self.log.tag_configure("item",    foreground="#222222")
        self.log.tag_configure("success", foreground=COLOR_SUCCESS, font=FONT_UI_BOLD)
        self.log.tag_configure("undo",    foreground=COLOR_WARNING)
        self.log.tag_configure("hint",    foreground=COLOR_HINT, font=("Segoe UI", 9, "italic"))

        log_vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_vsb.set, state="disabled")

        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Статусная строка внизу окна ---
        status_bar = tk.Frame(root, relief=tk.SUNKEN, bd=1)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_bar_var = tk.StringVar()
        self.status_bar_label = tk.Label(
            status_bar,
            textvariable=self.status_bar_var,
            anchor="w",
            font=("Segoe UI", 9),
            fg=COLOR_HINT,
            padx=8, pady=2,
        )
        self.status_bar_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.update_status()

        # --- Загрузка сохранённого состояния и обработчик закрытия ---
        self.load_state()

        # --- Меню (после загрузки, чтобы чекбокс отражал сохранённое значение) ---
        self._build_menu()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- Логика ----------
    def update_status(self):
        note = f" DataMatrix({self.CODE_LENGTH})"
        if self.current_set is None:
            next_num = self.set_counter + 1
            self.status_var.set(f"Ожидается КОД НАБОРА №{next_num}{note}")
            self.hint_var.set(f"После набора будет считано {self.items_per_set} кодов товаров")
        else:
            n = len(self.current_items) + 1
            self.status_var.set(
                f"Набор №{self.set_counter} "
#                f"Набор №{self.set_counter}: {self.current_set}  "
                f"|  Ожидается ТОВАР {n} из {self.items_per_set}{note}"
            )
            self.hint_var.set("Сканируйте код товара, входящего в набор")
        if hasattr(self, "status_bar_var"):
            self.update_status_bar()

    def update_status_bar(self):
        """Обновить нижнюю статусную строку: счётчики наборов и товаров."""
        saved_sets = len({setcode for _, setcode in self.rows})
        saved_items = len(self.rows)
        current = 1 if self.current_set is not None else 0

        text = (
            f"Создано наборов: {saved_sets}   |   "
            f"Сохранено товаров: {saved_items}"
        )
        if current:
            text += (
                f"   |   В работе: набор №{self.set_counter} "
                f"({len(self.current_items)}/{self.items_per_set})"
            )
        self.status_bar_var.set(text)

    def _build_menu(self):
        """Меню в заголовке окна: Настройки → ..., Справка → О программе."""
        menubar = tk.Menu(self.root)

        # --- Файл ---
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Открыть CSV…",
            command=self.open_csv,
            accelerator="Ctrl+O",
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Выход",
            command=self.on_close,
            accelerator="Alt+F4",
        )
        menubar.add_cascade(label="Файл", menu=file_menu)

        # --- Настройки ---
        settings_menu = tk.Menu(menubar, tearoff=0)
        self.dup_var = tk.BooleanVar(value=self.check_duplicates)
        settings_menu.add_checkbutton(
            label="Проверять дубликаты кодов",
            variable=self.dup_var,
            command=self.on_toggle_duplicates,
        )
        menubar.add_cascade(label="Настройки", menu=settings_menu)

        # --- Справка ---
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label="О программе",
            command=self.show_about,
        )
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.root.config(menu=menubar)

        # Горячая клавиша Ctrl+O
        self.root.bind("<Control-o>", lambda e: self.open_csv())

    def on_toggle_duplicates(self):
        """Переключение настройки проверки дубликатов."""
        self.check_duplicates = bool(self.dup_var.get())
        state = "включена" if self.check_duplicates else "отключена"
        self.log_line(f"[настройка] проверка дубликатов {state}", tag="hint")
        self.save_state()

    def sync_items_spin(self):
        """Spinbox доступен только когда текущий набор не начат."""
        if self.current_set is None:
            self.items_spin.configure(state="normal")
        else:
            self.items_spin.configure(state="disabled")

    def log_line(self, text, tag=None):
        self.log.configure(state="normal")
        if tag:
            self.log.insert(tk.END, text + "\n", tag)
        else:
            self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def on_items_changed(self):
        """Пользователь поменял количество товаров в наборе."""
        if self.current_set is not None:
            # страховка: в норме сюда не попадём — Spinbox disabled
            self.items_var.set(self.items_per_set)
            return

        try:
            value = int(self.items_var.get())
        except (tk.TclError, ValueError):
            value = self.items_per_set
        value = max(1, min(100, value))
        self.items_per_set = value
        self.items_var.set(value)
        self.update_status()

    def _is_duplicate_code(self, code: str) -> bool:
        """True, если code уже встречался как код набора или код товара."""
        # сохранённые пары (товар, набор)
        for item, setcode in self.rows:
            if code == item or code == setcode:
                return True
        # текущий незавершённый набор
        if self.current_set is not None and code == self.current_set:
            return True
        if code in self.current_items:
            return True
        return False
 
    def on_enter(self, event=None):
        code = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        if not code:
            return

        # --- обрезка до первых CODE_LENGTH символов ---
        if len(code) > self.CODE_LENGTH:
            code = code[:self.CODE_LENGTH]
        # ---------------------------------------------

        # --- проверка дубликатов ---
        if self.check_duplicates and self._is_duplicate_code(code):
            self.log_line(
                f"[ДУБЛИКАТ] код уже введён ранее: {code}", tag="undo"
            )
            messagebox.showwarning(
                "Дубликат кода",
                f"Код уже был введён ранее:\n\n{code}\n\n"
                f"Повторный ввод не допускается."
            )
            self.entry.focus_set()
            return
        # ---------------------------------------------


        if self.current_set is None:
            # Пришёл код набора
            self.set_counter += 1
            self.current_set = code
            self.current_items = []
            self.log_line(f"[НАБОР №{self.set_counter}]  {code}", tag="set")
        else:
            # Пришёл код товара
            self.current_items.append(code)
            self.log_line(f"   [ТОВАР {len(self.current_items)}] {code}", tag="item")

            if len(self.current_items) >= self.items_per_set:
                # Набор укомплектован — сохраняем и начинаем новый
                for item in self.current_items:
                    self.rows.append((item, self.current_set))
                self.log_line(
                    f"→ Набор №{self.set_counter} {self.current_set} сохранён "
                    f"({self.items_per_set} товара)\n", tag="success"
                )
                self.current_set = None
                self.current_items = []

        self.sync_items_spin()      # Блокировка кол-ва товаров в наборе
        self.update_status()

    def undo_last(self):
        """Откатить последнее действие."""
        # 1. Если есть недобранные товары в текущем наборе — убираем последний
        if self.current_items:
            removed = self.current_items.pop()
            self.log_line(f"[отмена] удалён товар {removed}", tag="undo")
        # 2. Если набор начат, но товаров ещё нет — убираем набо
        elif self.current_set is not None:
            self.log_line(f"[отмена] удалён набор №{self.set_counter} {self.current_set}")
            self.current_set = None
            self.current_items = []
            self.set_counter -= 1
        # 3. Иначе откатываем последний сохранённый набор целиком
        elif self.rows:
            # Собираем все товары последнего набора (они лежат подряд в rows)
            last_set = self.rows[-1][1]
            restored_items = []
            while self.rows and self.rows[-1][1] == last_set:
                item, _ = self.rows.pop()
                restored_items.append(item)
            restored_items.reverse()  # возвращаем исходный порядок

            # Восстанавливаем состояние: набор «в работе», товары — все, кроме последнего
            self.current_set = last_set
            self.current_items = restored_items[:-1]  # последний товар «отменяем»
            removed = restored_items[-1]
            self.log_line(
                f"[отмена] набор {last_set} возвращён в работу, "
                f"удалён товар {removed}", tag="undo"
            )
            # set_counter не трогаем — набор уже был учтён

        else:
            self.log_line("[отмена] нечего отменять")

        self.sync_items_spin()      # Блокировка кол-ва товаров в наборе
        self.update_status()

    def reset_all(self):
        if messagebox.askyesno("Сброс", "Удалить все введённые данные?"):
            self.rows.clear()
            self.current_set = None
            self.current_items = []
            self.set_counter = 0
#            self.items_per_set = 3
#            self.items_var.set(3)
            self.log.configure(state="normal")
            self.log.delete("1.0", tk.END)
            self.log.configure(state="disabled")

            self.sync_items_spin()      # Блокировка кол-ва товаров в наборе
            self.update_status()

    def finish(self):
        if not self.rows:
            messagebox.showinfo("Нет данных", "Не введено ни одной записи.")
            return
        if self.current_set is not None:
            if not messagebox.askyesno(
                "Незавершённый набор",
                f"Набор {self.current_set} не укомплектован "
                f"({len(self.current_items)} из {self.items_per_set}).\n"
                f"Продолжить вывод таблицы без него?"
            ):
                return
            # пользователь согласился «выбросить» недобранный набор
            self.current_set = None
            self.current_items = []

        self.sync_items_spin()      # Блокировка кол-ва товаров в наборе
        ResultWindow(self.root, self.rows)

    # ---------- Открытие CSV ----------
    def open_csv(self):
        """Открыть ранее сохранённый CSV и загрузить его как наборы."""
        # 1. Защита от потери текущих данных
        has_data = bool(self.rows) or self.current_set is not None
        if has_data:
            if not messagebox.askyesno(
                "Открыть CSV",
                "Текущие данные будут заменены содержимым файла.\n\n"
                "Продолжить?",
            ):
                return

        # 2. Выбор файла
        path = filedialog.askopenfilename(
            title="Открыть CSV с результатами",
            filetypes=[("CSV", "*.csv"), ("Все файлы", "*.*")],
        )
        if not path:
            return

        # 3. Чтение
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f, delimiter=";")
                raw_rows = list(reader)
        except OSError as e:
            messagebox.showerror(
                "Не удалось открыть файл",
                f"{path}\n\n{e}",
            )
            return
        except UnicodeDecodeError:
            # на случай, если файл сохранён в cp1251 (например, старым Excel)
            try:
                with open(path, "r", newline="", encoding="cp1251") as f:
                    reader = csv.reader(f, delimiter=";")
                    raw_rows = list(reader)
            except Exception as e:
                messagebox.showerror(
                    "Не удалось прочитать файл",
                    f"{path}\n\nПохоже, кодировка не UTF-8 и не CP1251.\n{e}",
                )
                return

        if not raw_rows:
            messagebox.showinfo("Пустой файл", "Файл не содержит данных.")
            return

        # 4. Разбор строк: пропускаем заголовок, если он есть
        header = raw_rows[0]
        start_idx = 0
        if header and len(header) >= 2:
            h0 = header[0].strip().lower()
            h1 = header[1].strip().lower()
            if h0.startswith("код") and "набор" in h1:
                start_idx = 1  # это наш заголовок «Код;Код набора»

        new_rows = []
        seen_items = set()
        seen_sets = set()
        skipped_invalid = 0
        skipped_duplicates = 0
        skipped_self = 0

        for row in raw_rows[start_idx:]:
            if not row or all(not c.strip() for c in row):
                continue
            if len(row) < 2:
                skipped_invalid += 1
                continue
            item = row[0].strip()
            setcode = row[1].strip()
            if not item or not setcode:
                skipped_invalid += 1
                continue
            # обрезка как в on_enter — на случай «длинных» кодов из других источников
            if len(item) > self.CODE_LENGTH:
                item = item[: self.CODE_LENGTH]
            if len(setcode) > self.CODE_LENGTH:
                setcode = setcode[: self.CODE_LENGTH]
            # код товара не может совпадать с кодом набора
            if item == setcode:
                skipped_self += 1
                continue
            # дубликаты (учитываем настройку)
            if self.check_duplicates:
                if item in seen_items or setcode in seen_items or item in seen_sets:
                    skipped_duplicates += 1
                    continue
            new_rows.append((item, setcode))
            seen_items.add(item)
            seen_sets.add(setcode)

        if not new_rows:
            messagebox.showwarning(
                "Нет данных для загрузки",
                "В файле не найдено ни одной корректной пары «товар;набор».\n\n"
                f"Пропущено строк: {skipped_invalid + skipped_duplicates + skipped_self}",
            )
            return

        # 5. Применяем: заменяем rows, сбрасываем текущий набор и счётчики
        self.rows = new_rows
        self.current_set = None
        self.current_items = []
        self.set_counter = len({s for _, s in new_rows})

        # 6. Перерисовываем UI
        self.rebuild_log()
        self.sync_items_spin()
        self.update_status()

        # 7. Итог
        summary = (
            f"Файл: {os.path.basename(path)}\n\n"
            f"Загружено пар: {len(new_rows)}\n"
            f"Наборов: {self.set_counter}"
        )
        if skipped_invalid:
            summary += f"\nПропущено некорректных строк: {skipped_invalid}"
        if skipped_duplicates:
            summary += f"\nПропущено дубликатов: {skipped_duplicates}"
        if skipped_self:
            summary += f"\nПропущено строк, где товар = набор: {skipped_self}"
        messagebox.showinfo("CSV загружен", summary)

        self.log_line(
            f"[открыт CSV] {os.path.basename(path)}: "
            f"{len(new_rows)} пар, {self.set_counter} наборов",
            tag="hint",
        )

    # ---------- Сохранение / загрузка состояния ----------
    def save_state(self):
        """Сохранить состояние в JSON. Ошибки — в диалог, но не падать."""
        state = {
            "format_version": STATE_FORMAT_VERSION, 
            "app_version": APP_VERSION,
            "geometry": self.root.geometry(),
            "items_per_set": self.items_per_set,
            "code_length": self.CODE_LENGTH,
            "check_duplicates": self.check_duplicates,
            "set_counter": self.set_counter,
            "current_set": self.current_set,
            "current_items": self.current_items,
            "rows": self.rows,
        }
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except OSError as e:
            messagebox.showwarning(
                "Не удалось сохранить состояние",
                f"{STATE_FILE}\n\n{e}"
            )

    def load_state(self):
        """Загрузить состояние из JSON. Если файла нет — тихо выходим."""
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showwarning(
                "Не удалось загрузить состояние",
                f"{STATE_FILE}\n\n{e}\n\nБудут использованы настройки по умолчанию."
            )
            return

        # --- проверка совместимости формата ---
        fmt = int(state.get("format_version", 1))
        if fmt > STATE_FORMAT_VERSION:
            if not messagebox.askyesno(
                "Несовместимый формат состояния",
                f"Файл состояния создан более новой версией программы\n"
                f"(формат {fmt}, поддерживается до {STATE_FORMAT_VERSION}).\n\n"
                f"Продолжить загрузку? Часть данных может быть потеряна."
            ):
                return

        # --- геометрия окна ---
        geom = state.get("geometry")
        if geom:
            try:
                self.root.geometry(geom)
            except tk.TclError:
                pass

        # --- количество товаров в наборе ---
        ips = state.get("items_per_set", 3)
        if isinstance(ips, int) and 1 <= ips <= 100:
            self.items_per_set = ips
        self.items_var.set(self.items_per_set)

        # --- длина кода ---
        cl = state.get("code_length", self.CODE_LENGTH)
        if isinstance(cl, int) and cl > 0:
            self.CODE_LENGTH = cl

        # --- счётчик и текущий набор ---
        self.set_counter = int(state.get("set_counter", 0))

        cur_set = state.get("current_set")
        if isinstance(cur_set, str) and cur_set:
            self.current_set = cur_set
        else:
            self.current_set = None

        cur_items = state.get("current_items") or []
        if isinstance(cur_items, list):
            self.current_items = [str(x) for x in cur_items]
        else:
            self.current_items = []

        # --- сохранённые строки ---
        rows = state.get("rows") or []
        self.rows = []
        for entry in rows:
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                self.rows.append((str(entry[0]), str(entry[1])))

        # --- проверка дубликатов ---
        cd = state.get("check_duplicates", True)
        self.check_duplicates = bool(cd)
        if hasattr(self, "dup_var"):
            self.dup_var.set(self.check_duplicates)

        # --- перерисовать журнал и синхронизировать UI ---
        self.rebuild_log()
        self.sync_items_spin()
        self.update_status()

    def rebuild_log(self):
        """Восстановить содержимое журнала по текущему состоянию."""
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)

        # сохранённые наборы — группируем по коду набора, сохраняя порядок
        if self.rows:
            seen = []
            groups = {}
            for item, setcode in self.rows:
                if setcode not in groups:
                    groups[setcode] = []
                    seen.append(setcode)
                groups[setcode].append(item)
            for idx, setcode in enumerate(seen, start=1):
                self.log.insert(tk.END, f"[НАБОР №{idx}]  {setcode}\n", "set")
                for item in groups[setcode]:
                    self.log.insert(tk.END, f"   [ТОВАР] {item}\n", "item")
                self.log.insert(tk.END, "→ сохранён\n", "success")

        # текущий (незавершённый) набор
        if self.current_set is not None:
            self.log.insert(
                tk.END,
                f"[НАБОР №{self.set_counter}]  {self.current_set}  "
                f"(в работе)\n", "set"
            )
            for i, item in enumerate(self.current_items, start=1):
                self.log.insert(tk.END, f"   [ТОВАР {i}] {item}\n", "item")

        self.log.configure(state="disabled")
        self.log.see(tk.END)

    def on_close(self):
        """Сохранить состояние и закрыть окно."""
        self.save_state()
        self.root.destroy()

    def show_about(self):
        """Окно «О программе» — версия и путь к state.json."""
        messagebox.showinfo(
            f"О программе — {APP_NAME}",
            f"{APP_TITLE}\n\n"
            f"Версия программы: {APP_VERSION}\n"
            f"Формат файла состояния: {STATE_FORMAT_VERSION}\n\n"
            f"Файл состояния:\n{STATE_FILE}\n\n"
            f"Python: {sys.version.split()[0]}\n"
            f"Платформа: {sys.platform}",
#            icon="question"   # что бы убрать системный звук (иконки info)
        )


class ResultWindow:
    def __init__(self, parent, rows):
        self.rows = rows
        self.win = tk.Toplevel(parent)
        self.win.title("Результат — сопоставление товаров и наборов")
        self.win.geometry("700x500")

        tk.Label(
            self.win, text="Код товара  →  Код набора",
            font=("Segoe UI", 12, "bold")
        ).pack(pady=8)

        frame = tk.Frame(self.win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("item", "set")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        self.tree.heading("item", text="Код товара")
        self.tree.heading("set", text="Код набора")
        self.tree.column("item", width=320, anchor="w")
        self.tree.column("set", width=320, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        for item, setcode in rows:
            self.tree.insert("", tk.END, values=(item, setcode))

        # --- Контекстное меню и горячие клавиши для копирования ---
        self._build_context_menu()

        btn_frame = tk.Frame(self.win)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Сохранить в CSV", width=20,
                  command=self.save_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Сохранить в Excel (TSV)", width=22,
                  command=self.save_tsv).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Закрыть", width=15,
                  command=self.win.destroy).pack(side=tk.LEFT, padx=5)

    def grouped_rows(self):
        """Группирует строки по набору в порядке появления.
        Возвращает список строк для CSV:
        [ (код_набора, ""), (код_товара, код_набора), ... , (код_набора2, ""), ... ]
        """
        result = []
        seen_order = []
        groups = {}

        for item, setcode in self.rows:
            if setcode not in groups:
                groups[setcode] = []
                seen_order.append(setcode)
            groups[setcode].append(item)

        for setcode in seen_order:
            # строка-заголовок набора: код в левой колонке, правая пустая
            result.append((setcode, ""))
            for item in groups[setcode]:
                result.append((item, setcode))

        return result

    # ---------- Контекстное меню и копирование ----------
    def _build_context_menu(self):
        """Создать контекстное меню для Treeview и повесить обработчики."""
        self.ctx_menu = tk.Menu(self.win, tearoff=0)
        self.ctx_menu.add_command(
            label="Копировать выделенное",
            command=self.copy_selected,
            accelerator="Ctrl+C",
        )
        self.ctx_menu.add_command(
            label="Копировать всё",
            command=self.copy_all,
        )
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(
            label="Выделить всё",
            command=self.select_all,
            accelerator="Ctrl+A",
        )

        # Правый клик — показать меню
        self.tree.bind("<Button-3>", self._show_context_menu)
        # Горячие клавиши
        self.tree.bind("<Control-c>", lambda e: self.copy_selected())
        self.tree.bind("<Control-a>", lambda e: self.select_all())
        # Ctrl+Insert — классическая альтернатива копирования в Windows
        self.tree.bind("<Control-Insert>", lambda e: self.copy_selected())

        # Перехват правого клика и на дочернем окне (на случай фокуса вне Treeview)
        self.win.bind("<Control-c>", lambda e: self.copy_selected())

    def _show_context_menu(self, event):
        """Показать контекстное меню в позиции курсора."""
        # Если кликнули по строке, которой нет в выделении — выделяем её
        row_id = self.tree.identify_row(event.y)
        if row_id and row_id not in self.tree.selection():
            self.tree.selection_set(row_id)
        try:
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    def _rows_to_tsv(self, selection=None) -> str:
        """
        Собрать данные Treeview в TSV.
        selection=None — все строки; иначе — только перечисленные iid.
        Возвращает строку с '\\t' между колонками и '\\n' между строками.
        """
        if selection is None:
            iids = self.tree.get_children("")
        else:
            # сохраняем порядок как в таблице, а не как пришло из selection()
            all_iids = self.tree.get_children("")
            sel_set = set(selection)
            iids = [iid for iid in all_iids if iid in sel_set]

        lines = []
        for iid in iids:
            values = self.tree.item(iid, "values")
            # На всякий случай приводим к строкам и экранируем табы/переводы строк
            safe = [
                str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")
                for v in values
            ]
            lines.append("\t".join(safe))
        return "\n".join(lines)

    def copy_selected(self):
        """Скопировать выделенные строки в буфер обмена как таблицу (TSV)."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo(
                "Нечего копировать",
                "Выделите одну или несколько строк в таблице.",
                parent=self.win,
            )
            return
        data = self._rows_to_tsv(selection)
        self._copy_to_clipboard(data, f"Скопировано строк: {len(selection)}")

    def copy_all(self):
        """Скопировать всю таблицу в буфер обмена как таблицу (TSV)."""
        iids = self.tree.get_children("")
        if not iids:
            messagebox.showinfo(
                "Нечего копировать",
                "Таблица пуста.",
                parent=self.win,
            )
            return
        data = self._rows_to_tsv(None)
        self._copy_to_clipboard(data, f"Скопировано строк: {len(iids)}")

    def select_all(self):
        """Выделить все строки в таблице."""
        self.tree.selection_set(self.tree.get_children(""))

    def _copy_to_clipboard(self, text: str, status_msg: str):
        """Положить text в буфер обмена и кратко сообщить в заголовке окна."""
        if not text:
            return
        self.win.clipboard_clear()
        self.win.clipboard_append(text)
        # Важно: clipboard в Tk живёт, пока живёт процесс. Для надёжности
        # можно обновлять через update, но Tkinter сам держит буфер.
        self.win.update_idletasks()

        # Кратковременная обратная связь: меняем заголовок окна на 1.5 секунды
        old_title = self.win.title()
        self.win.title(f"✔ {status_msg}")
        self.win.after(1500, lambda: self.win.title(old_title))
    # ------------------------------------------------

#    def save_csv(self):
#        path = filedialog.asksaveasfilename(
#            defaultextension=".csv",
#            filetypes=[("CSV", "*.csv")],
#            initialfile="marking_result.csv"
#        )
#        if not path:
#            return
#        with open(path, "w", newline="", encoding="utf-8-sig") as f:
#            w = csv.writer(f, delimiter=";")
#            w.writerow(["Код товара", "Код набора"])
#            for item, setcode in self.rows:
#                w.writerow([item, setcode])
#        messagebox.showinfo("Сохранено", f"Файл сохранён:\n{path}")

    def save_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="marking_result.csv"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Код", "Код набора"])
            for item, setcode in self.rows:
                w.writerow([item, setcode])
#           Вариант с указанием в файле выгрузки сначала кода маркировки набора, а потом состава набора
#            for left, right in self.grouped_rows():
#                w.writerow([left, right])
        messagebox.showinfo("Сохранено", f"Файл сохранён:\n{path}")

    def save_tsv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xls",
            filetypes=[("Excel (TSV)", "*.xls"), ("Все файлы", "*.*")],
            initialfile="marking_result.xls"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("Код товара\tКод набора\n")
            for item, setcode in self.rows:
                f.write(f"{item}\t{setcode}\n")
        messagebox.showinfo("Сохранено", f"Файл сохранён:\n{path}")


if __name__ == "__main__":
    root = tk.Tk()
    app = BundlePackerApp(root)
    root.mainloop()