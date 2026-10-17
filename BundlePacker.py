import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv

class MarkingApp:
    ITEMS_PER_SET = 3  # сколько товаров в наборе
    CODE_LENGTH = 31   # сколько первых символов сохраняем

    def __init__(self, root):
        self.root = root
        self.root.title("Сопоставление кодов маркировки")
        self.root.geometry("700x550")

        # Данные: список кортежей (код_товара, код_набора)
        self.rows = []

        # Текущее состояние ввода
        self.current_set = None
        self.current_items = []
        self.set_counter = 0     # сколько наборов уже начато

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

        # --- Журнал ввода (что уже отсканировано) ---
        tk.Label(root, text="Журнал ввода:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10)
        self.log = tk.Text(root, height=8, font=("Consolas", 10))
        self.log.pack(fill=tk.X, padx=10, pady=5)
        self.log.configure(state="disabled")

        self.update_status()

    # ---------- Логика ----------
    def update_status(self):
        note = f"  (сохраняются первые {self.CODE_LENGTH} символов)"
        if self.current_set is None:
            next_num = self.set_counter + 1
            self.status_var.set(f"Ожидается КОД НАБОРА №{next_num}{note}")
            self.hint_var.set(f"После набора будет считано {self.ITEMS_PER_SET} кодов товаров")
        else:
            n = len(self.current_items) + 1
            self.status_var.set(
                f"Набор №{self.set_counter}: {self.current_set}  "
                f"|  Ожидается ТОВАР {n} из {self.ITEMS_PER_SET}{note}"
            )
            self.hint_var.set("Сканируйте код товара, входящего в набор")

    def log_line(self, text):
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def on_enter(self, event=None):
        code = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        if not code:
            return

        # --- обрезка до первых CODE_LENGTH символов ---
        if len(code) > self.CODE_LENGTH:
            code = code[:self.CODE_LENGTH]
        # ---------------------------------------------

        if self.current_set is None:
            # Пришёл код набора
            self.set_counter += 1
            self.current_set = code
            self.current_items = []
            self.log_line(f"[НАБОР №{self.set_counter}]  {code}")
        else:
            # Пришёл код товара
            self.current_items.append(code)
            self.log_line(f"   [ТОВАР {len(self.current_items)}] {code}")

            if len(self.current_items) >= self.ITEMS_PER_SET:
                # Набор укомплектован — сохраняем и начинаем новый
                for item in self.current_items:
                    self.rows.append((item, self.current_set))
                self.log_line(
                    f"→ Набор №{self.set_counter} {self.current_set} сохранён "
                    f"({self.ITEMS_PER_SET} товара)\n"
                )
                self.current_set = None
                self.current_items = []

        self.update_status()

    def undo_last(self):
        """Откатить последнее действие."""
        if self.current_items:
            removed = self.current_items.pop()
            self.log_line(f"[отмена] удалён товар {removed}")
        elif self.current_set is not None:
            self.log_line(f"[отмена] удалён набор №{self.set_counter} {self.current_set}")
            self.current_set = None
            self.set_counter -= 1
        elif self.rows:
            item, setcode = self.rows.pop()
            self.current_set = setcode
            self.current_items = [item]  # вернёмся к состоянию до последнего товара
            # Восстановим остальные товары этого набора, если они уже были
            # (в текущей модели мы не храним их отдельно, поэтому просто оставим этот)
            self.log_line(f"[отмена] возвращён к набору {setcode}")
        self.update_status()

    def reset_all(self):
        if messagebox.askyesno("Сброс", "Удалить все введённые данные?"):
            self.rows.clear()
            self.current_set = None
            self.current_items = []
            self.set_counter = 0
            self.log.configure(state="normal")
            self.log.delete("1.0", tk.END)
            self.log.configure(state="disabled")
            self.update_status()

    def finish(self):
        if not self.rows:
            messagebox.showinfo("Нет данных", "Не введено ни одной записи.")
            return
        if self.current_set is not None:
            if not messagebox.askyesno(
                "Незавершённый набор",
                f"Набор {self.current_set} не укомплектован "
                f"({len(self.current_items)} из {self.ITEMS_PER_SET}).\n"
                f"Продолжить вывод таблицы без него?"
            ):
                return
        ResultWindow(self.root, self.rows)


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
            w.writerow(["Код товара", "Код набора"])
            for item, setcode in self.rows:
                w.writerow([item, setcode])
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
    app = MarkingApp(root)
    root.mainloop()