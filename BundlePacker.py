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
APP_VERSION = "1.2.5"

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
        tk.Button(frame_btn, text="Завершить и показать таблицу", width=28,
                  command=self.finish).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="О программе", width=15,
                  command=self.show_about).pack(side=tk.LEFT, padx=5)

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

    def _build_menu(self):
        """Меню в заголовке окна: Настройки → Проверять дубликаты."""
        menubar = tk.Menu(self.root)

        settings_menu = tk.Menu(menubar, tearoff=0)
        self.dup_var = tk.BooleanVar(value=self.check_duplicates)
        settings_menu.add_checkbutton(
            label="Проверять дубликаты кодов",
            variable=self.dup_var,
            command=self.on_toggle_duplicates,
        )
        menubar.add_cascade(label="Настройки", menu=settings_menu)

        self.root.config(menu=menubar)

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
            f"Платформа: {sys.platform}"
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