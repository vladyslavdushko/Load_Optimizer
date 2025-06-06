# import os
# os.environ["TCL_LIBRARY"] = "/opt/homebrew/opt/tcl-tk/lib/tcl8.6"
# os.environ["TK_LIBRARY"] = "/opt/homebrew/Cellar/tcl-tk/9.0.1/lib/tk9.0"
import time
import tkinter as tk
import threading, queue
from tkinter import messagebox, filedialog
from optimizer import Container, Item, PackingOptimizer
import matplotlib
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import platform
from tkinter import ttk
import json, os
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from db import init_db, save_session_to_db, list_sessions, load_fig_from_db, delete_session
import sqlite3

if platform.system() == 'Darwin':
    matplotlib.use('MacOSX')
else:
    matplotlib.use('TkAgg')

import matplotlib.pyplot as plt

DB_PATH = "sessions/packing_sessions.db"


# Простий клас для реалізації tooltip
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.widget.bind("<Enter>", self.showtip)
        self.widget.bind("<Leave>", self.hidetip)

    def showtip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # Отримуємо координати для розташування tooltip
        x, y, cx, cy = self.widget.bbox("insert") if self.widget.bbox("insert") else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        # Встановлюємо фон (наприклад, світло-жовтий) і явно задаємо чорний текст
        label = tk.Label(
            tw,
            text=self.text,
            justify='left',
            background="#cfcf0a",  # світло-жовтий фон
            foreground="black",    # чорний текст
            relief='solid',
            borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        label.pack(ipadx=1)

    def hidetip(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3D Bin Packing")
        self.geometry("1000x800")
        self.minsize(1000, 800)
        init_db()

        self.packed = False  # пакування ще не запускалось
        self.dirty = False  # чи є незбережені зміни після пакування
        self.visualization_open = False  # чи зараз відкрите 3D-вік

        self.container_data = None
        # self.boxes_data – список словників з даними коробок
        self.boxes_data = []  
        # summary_box – словник для зведеної інформації по коробкам {назва: {count, width, height, depth, weight}}
        self.summary_box = {}
        
        self.show_welcome_screen()
        self.progress_q = queue.Queue()

    def on_viz_close(self, win):
        win.destroy()
        self.visualization_open = False
        # якщо після останнього пакування були зміни — рахуємо їх «готовими» до повторного запуску
        if self.dirty:
            self.start_packing_button.config(state="normal")

    def show_welcome_screen(self):
        # очищуємо попередні фрейми
        for widget in self.winfo_children():
            widget.destroy()

        # Головний фрейм
        self.welcome_frame = tk.Frame(self)
        self.welcome_frame.pack(expand=True, fill='both', padx=10, pady=10)

        tk.Label(self.welcome_frame, text="Ласкаво просимо до 3D Bin Packing", font=("Arial", 16)).pack(pady=10)

        # Кнопка для нової сесії
        tk.Button(self.welcome_frame, text="Почати пакування", font=("Arial", 14),
                  command=self.show_configuration_screen).pack(pady=5)

        # Історія сесій
        tk.Label(self.welcome_frame, text="Історія пакувань:", font=("Arial", 12)).pack(pady=(20,5))
        self.history_tree = ttk.Treeview(self.welcome_frame, columns=("id","name","ts"), show="headings", height=8)
        self.history_tree.heading("id", text="ID")
        self.history_tree.heading("name", text="Назва")
        self.history_tree.heading("ts", text="Дата/час")
        self.history_tree.pack(fill="both", expand=True)

        # Заповнюємо історію
        for sess in list_sessions():
            self.history_tree.insert("", "end", iid=sess["id"], values=(sess["id"], sess["name"], sess["timestamp"]))

        # Show кнопка
        btn_frame = tk.Frame(self.welcome_frame)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Переглянути", command=self._on_history_show).pack(pady=5)
        tk.Button(btn_frame, text="Видалити", width=10, command=self._on_history_delete).pack(side="left", padx=5)

    def _on_history_show(self):
        sel = self.history_tree.focus()
        if not sel:
            messagebox.showinfo("Info", "Оберіть сесію зі списку")
            return
        self.load_and_show(int(sel))

    def _on_history_delete(self):
        sel = self.history_tree.focus()
        if not sel:
            messagebox.showinfo("Інфо", "Оберіть сесію для видалення")
            return

        # Підтвердження видалення
        name = self.history_tree.item(sel, "values")[1]
        if not messagebox.askyesno(
            "Підтвердження",
            f"Ви дійсно бажаєте видалити сесію:\n«{name}» (ID={sel})?"
        ):
            return

        # Видаляємо з БД і з дерева
        try:
            from db import delete_session
            delete_session(int(sel))
            self.history_tree.delete(sel)
            messagebox.showinfo("Готово", f"Сесію «{name}» видалено.")
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося видалити сесію: {e}")

    def load_and_show(self, session_id: int):
        try:
            # завантажуємо з БД container, boxes та packed_items
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(
                """
                SELECT container_json, packed_items_json
                FROM sessions WHERE id = ?
                """, (session_id,)
            )
            row = c.fetchone()
            conn.close()
            if not row:
                raise ValueError(f"Session {session_id} not found")

            cont_dict      = json.loads(row[0])
            packed_items   = json.loads(row[1])

            # створюємо контейнер і оптимізатор
            container = Container(
                width=cont_dict['width'],
                height=cont_dict['height'],
                depth=cont_dict['depth'],
                max_weight=cont_dict['max_weight']
            )
            optimizer = PackingOptimizer(container)

            # відновлюємо результат
            optimizer.packed_items = packed_items

            # обчислюємо заповнення простору для заголовка
            vol_sum = sum(
                item['size'][0] * item['size'][1] * item['size'][2]
                for item in packed_items
            )
            total_vol = (container.width *
                         container.depth *
                         container.height)
            optimizer.space_utilization = (vol_sum / total_vol) * 100

            # показуємо вікно з вашою функцією-«show_visualization»
            self.show_visualization(optimizer)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_configuration_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.config_frame = tk.Frame(self)
        self.config_frame.pack(expand=True, fill='both', padx=10, pady=10)

        # Назва сесії
        tk.Label(self.config_frame, text="Назва сесії:").grid(row=0, column=0, sticky='e', padx=5, pady=5)
        self.session_name_entry = tk.Entry(self.config_frame)
        self.session_name_entry.grid(row=0, column=1, padx=5, pady=5)

        # після створення config_frame
        self.config_frame.rowconfigure(0, weight=1)
        self.config_frame.columnconfigure(0, weight=3)
        self.config_frame.columnconfigure(1, weight=1)

        self.input_frame = tk.Frame(self.config_frame)
        self.input_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        self.box_list_frame = tk.LabelFrame(self.config_frame, text="Додані коробки", padx=5, pady=5)
        self.box_list_frame.grid(row=0, column=1)

        self.box_tree = ttk.Treeview(
            self.box_list_frame,
            columns=("name", "qty", "w", "h", "d", "weight"),
            show="headings", height=30
        )

        self.box_tree.heading("name", text="Назва")
        self.box_tree.heading("qty", text="К-ть")
        self.box_tree.heading("w", text="W")
        self.box_tree.heading("h", text="H")
        self.box_tree.heading("d", text="D")
        self.box_tree.heading("weight", text="Кг")
        # Після налаштування заголовків
        column_sizes = {
            "name": (120, 80),
            "qty": (50, 30),
            "w": (50, 30),
            "h": (50, 30),
            "d": (50, 30),
            "weight": (60, 40),
        }
        for col, (w, minw) in column_sizes.items():
            # width — початкова ширина; minwidth — мінімально допустима
            self.box_tree.column(col, width=w, minwidth=minw, anchor='center')

        self.box_tree.pack(fill="both")

        btn_frame = tk.Frame(self.box_list_frame)
        btn_frame.pack(pady=2)

        edit_btn = tk.Button(btn_frame, text="Змінити",command = self.edit_selected_box)
        edit_btn.pack(side=tk.LEFT, padx=5)

        delete_btn = tk.Button(btn_frame, text="Видалити", command = self.delete_selected_box)
        delete_btn.pack(side=tk.LEFT, padx=5)

        # Налаштування розтягування колонок
        self.config_frame.columnconfigure(0, weight=3)
        self.config_frame.columnconfigure(1, weight=1)

        # Кнопка «Назад»
        tk.Button(self.config_frame, text="← Назад",
                  command=self.show_welcome_screen).grid(row=0, column=2, sticky='nw', padx=5, pady=5)

        # Введення параметрів контейнера у input_frame
        container_label = tk.Label(self.input_frame, text="Розміри контейнера", font=("Arial", 14))
        container_label.grid(row=0, column=0, columnspan=2, pady=10)

        tk.Label(self.input_frame, text="Ширина:").grid(row=1, column=0, sticky='e', padx=5, pady=5)
        self.container_width_entry = tk.Entry(self.input_frame)
        self.container_width_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Висота:").grid(row=2, column=0, sticky='e', padx=5, pady=5)
        self.container_height_entry = tk.Entry(self.input_frame)
        self.container_height_entry.grid(row=2, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Глибина:").grid(row=3, column=0, sticky='e', padx=5, pady=5)
        self.container_depth_entry = tk.Entry(self.input_frame)
        self.container_depth_entry.grid(row=3, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Максимальна вага:").grid(row=4, column=0, sticky='e', padx=5, pady=5)
        self.container_max_weight_entry = tk.Entry(self.input_frame)
        self.container_max_weight_entry.grid(row=4, column=1, padx=5, pady=5)

        # Введення даних для коробок у input_frame
        boxes_label = tk.Label(self.input_frame, text="Додати коробки", font=("Arial", 14))
        boxes_label.grid(row=5, column=0, columnspan=2, pady=10)

        tk.Label(self.input_frame, text="Назва коробки:").grid(row=6, column=0, sticky='e', padx=5, pady=5)
        self.box_name_entry = tk.Entry(self.input_frame)
        self.box_name_entry.grid(row=6, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Ширина:").grid(row=7, column=0, sticky='e', padx=5, pady=5)
        self.box_width_entry = tk.Entry(self.input_frame)
        self.box_width_entry.grid(row=7, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Висота:").grid(row=8, column=0, sticky='e', padx=5, pady=5)
        self.box_height_entry = tk.Entry(self.input_frame)
        self.box_height_entry.grid(row=8, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Глибина:").grid(row=9, column=0, sticky='e', padx=5, pady=5)
        self.box_depth_entry = tk.Entry(self.input_frame)
        self.box_depth_entry.grid(row=9, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Вага:").grid(row=10, column=0, sticky='e', padx=5, pady=5)
        self.box_weight_entry = tk.Entry(self.input_frame)
        self.box_weight_entry.grid(row=10, column=1, padx=5, pady=5)

        tk.Label(self.input_frame, text="Кількість:").grid(row=11, column=0, sticky='e', padx=5, pady=5)
        self.box_quantity_entry = tk.Entry(self.input_frame)
        self.box_quantity_entry.grid(row=11, column=1, padx=5, pady=5)

        add_box_button = tk.Button(
            self.input_frame,
            text="Додати коробку",
            command=self.add_box
        )

        add_box_button.grid(row=12, column=0, columnspan=2, pady=10)

        load_json_btn = tk.Button(
            self.input_frame, text="Зчитати JSON",
            command=self.load_from_json
        )
        load_json_btn.grid(row=13, column=0, columnspan=2, pady=10)

        # Перед кнопкою "Почати упаковку"
        tk.Label(self.input_frame, text="Назва сесії:").grid(row=5, column=0, sticky='e', padx=5, pady=5)
        self.session_name_entry = tk.Entry(self.input_frame)
        self.session_name_entry.grid(row=5, column=1, padx=5, pady=5)

        # Кнопка для запуску процесу упаковки – вона завжди активна, якщо хоча б одна коробка додана
        self.start_packing_button = tk.Button(
            self.input_frame,
            text="Почати упаковку",
            command=self.start_packing,
            state="disabled"  # спочатку вимкнена, поки не додано хоча б одну коробку
        )

        self.progress = ttk.Progressbar(
            self.input_frame, orient='horizontal',
            length=200, mode='determinate'
        )

        self.progress.grid(row=15, column=0, columnspan=2, pady=5)
        self.progress_lbl = tk.Label(self.input_frame, text="")
        self.progress_lbl.grid(row=16, column=0, columnspan=2)

        self.start_packing_button.grid(row=14, column=0, columnspan=2, pady=10)

        # Оновлення правого блоку зі списком коробок
        self.update_box_list()

    def load_from_json(self):
        path = filedialog.askopenfilename(
            title="Виберіть JSON‑файл",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list) or len(data) < 2:
                raise ValueError("JSON повинен містити контейнер + щонайменше 1 коробку")

            # ---------- контейнер ----------
            cont = data[0]
            for key in ("width", "height", "depth", "max_weight"):
                if key not in cont:
                    raise ValueError(f"Контейнеру бракує поля '{key}'")

            # заповнюємо поля вводу
            self.container_width_entry.delete(0, tk.END);  self.container_width_entry.insert(0, cont["width"])
            self.container_height_entry.delete(0, tk.END); self.container_height_entry.insert(0, cont["height"])
            self.container_depth_entry.delete(0, tk.END);  self.container_depth_entry.insert(0, cont["depth"])
            self.container_max_weight_entry.delete(0, tk.END); self.container_max_weight_entry.insert(0, cont["max_weight"])

            # ---------- коробки ----------
            self.boxes_data.clear()
            self.summary_box.clear()

            for box in data[1:]:
                for key in ("name", "width", "height", "depth", "weight", "quantity"):
                    if key not in box:
                        raise ValueError(f"Коробці бракує поля '{key}'")

                self.boxes_data.append(box)
                self.summary_box.setdefault(box["name"], {
                    "width": box["width"], "height": box["height"],
                    "depth": box["depth"], "weight": box["weight"], "count": 0
                })
                self.summary_box[box["name"]]["count"] += box["quantity"]

            self.update_box_list()
            self.start_packing_button.config(state="normal")

            messagebox.showinfo("Готово", f"Зчитано {len(self.boxes_data)} коробок з файлу.")
        except Exception as e:
            messagebox.showerror("Помилка JSON", str(e))

    def add_box(self):
        # Спочатку зчитуємо параметри контейнера з форми
        try:
            container_width = float(self.container_width_entry.get())
            container_height = float(self.container_height_entry.get())
            container_depth = float(self.container_depth_entry.get())
            container_max_weight = float(self.container_max_weight_entry.get())
        except ValueError:
            messagebox.showerror("Помилка", "Введіть коректні параметри контейнера перед додаванням коробок.")
            return

        # Зчитування даних про коробку
        box_name = self.box_name_entry.get().strip()
        if not box_name:
            messagebox.showerror("Помилка", "Введіть назву коробки.")
            return
        try:
            box_width = float(self.box_width_entry.get())
            box_height = float(self.box_height_entry.get())
            box_depth = float(self.box_depth_entry.get())
            box_weight = float(self.box_weight_entry.get())
            box_quantity = int(self.box_quantity_entry.get())
        except ValueError:
            messagebox.showerror("Помилка", "Будь ласка, введіть коректні числові значення для коробки.")
            return

        # Перевірка розмірів коробки відносно контейнера
        if box_width > container_width:
            messagebox.showerror("Помилка", "Ширина коробки перевищує ширину контейнера. Дана коробка не підходить.")
            return
        if box_height > container_height:
            messagebox.showerror("Помилка", "Висота коробки перевищує висоту контейнера. Дана коробка не підходить.")
            return
        if box_depth > container_depth:
            messagebox.showerror("Помилка", "Глибина коробки перевищує глибину контейнера. Дана коробка не підходить.")
            return

        # Перевірка ваги коробки (окремо)
        if box_weight > container_max_weight:
            messagebox.showerror("Помилка", "Вага коробки перевищує максимальну вагу контейнера.")
            return

        # Якщо всі перевірки пройдені, створюємо словник з даними коробки
        box_data = {
            "name": box_name,
            "width": box_width,
            "height": box_height,
            "depth": box_depth,
            "weight": box_weight,
            "quantity": box_quantity
        }
        self.boxes_data.append(box_data)

        # Оновлення зведеної інформації для відображення списку доданих коробок
        if box_name in self.summary_box:
            self.summary_box[box_name]['count'] += box_quantity
        else:
            self.summary_box[box_name] = {
                "count": box_quantity,
                "width": box_width,
                "height": box_height,
                "depth": box_depth,
                "weight": box_weight
            }

        messagebox.showinfo("Інформація", f"Коробку '{box_name}' додано.")

        # Очищення полів введення після додавання
        self.box_name_entry.delete(0, tk.END)
        self.box_width_entry.delete(0, tk.END)
        self.box_height_entry.delete(0, tk.END)
        self.box_depth_entry.delete(0, tk.END)
        self.box_weight_entry.delete(0, tk.END)
        self.box_quantity_entry.delete(0, tk.END)

        # Активуємо кнопку "Почати упаковку", якщо хоча б одна коробка додана
        self.start_packing_button.config(state="normal")
        # Оновлюємо список доданих коробок (метод update_box_list() вже має бути реалізований)
        self.update_box_list()
        self.mark_dirty()

    def update_box_list(self):
        # Очищаємо всі поточні рядки
        for row in self.box_tree.get_children():
            self.box_tree.delete(row)

        # Додаємо знову всі коробки з актуальними даними
        for box in self.boxes_data:
            self.box_tree.insert(
                '',
                'end',
                values=(
                    box['name'],
                    box['quantity'],
                    box['width'],
                    box['height'],
                    box['depth'],
                    box['weight']
                )
            )

    def edit_selected_box(self):
        selected = self.box_tree.selection()
        if not selected:
            messagebox.showwarning("Увага", "Оберіть коробку для редагування")
            return

        # Отримуємо значення вибраного рядка (ім’я коробки)
        row_id = selected[0]
        name = self.box_tree.item(row_id)['values'][0]

        # Знаходимо об'єкт коробки у self.boxes_data за іменем
        for box in self.boxes_data:
            if box['name'] == name:
                selected_box = box
                break
        else:
            messagebox.showerror("Помилка", f"Не знайдено коробку '{name}'")
            return

        # Створюємо модальне вікно для редагування
        modal = tk.Toplevel(self)
        modal.title("Редагування коробки")
        modal.grab_set()

        # Підготовка полів для редагування
        fields = [
            ("Name",     selected_box['name']),
            ("Quantity", selected_box['quantity']),
            ("Width",    selected_box['width']),
            ("Height",   selected_box['height']),
            ("Depth",    selected_box['depth']),
            ("Weight",   selected_box['weight']),
        ]
        entries = {}
        for r, (label, val) in enumerate(fields):
            tk.Label(modal, text=label).grid(row=r, column=0, padx=5, pady=5, sticky='e')
            ent = tk.Entry(modal)
            ent.insert(0, val)
            ent.grid(row=r, column=1, padx=5, pady=5)
            entries[label.lower()] = ent

        # Функція збереження змін
        def save_changes():
            try:
                selected_box['name']     = entries['name'].get().strip()
                selected_box['quantity'] = int(entries['quantity'].get())
                selected_box['width']    = float(entries['width'].get())
                selected_box['height']   = float(entries['height'].get())
                selected_box['depth']    = float(entries['depth'].get())
                selected_box['weight']   = float(entries['weight'].get())
            except ValueError:
                messagebox.showerror("Помилка", "Некоректні значення полів")
                return

            # Оновлюємо відображення таблиці
            self.update_box_list()
            self.mark_dirty()
            modal.destroy()

        # Кнопка збереження
        btn_save = tk.Button(modal, text="Зберегти", command=save_changes)
        btn_save.grid(row=len(fields), column=0, columnspan=2, pady=10)

    def delete_selected_box(self):
        selected = self.box_tree.selection()
        if not selected:
            messagebox.showwarning("Увага", "Оберіть коробку для видалення")
            return

        row_id = selected[0]
        name = self.box_tree.item(row_id)['values'][0]
        # Підтвердження видалення
        if not messagebox.askyesno("Підтвердження", f"Видалити коробку '{name}'?"):
            return

        # Видаляємо з даних і оновлюємо відображення
        self.boxes_data = [box for box in self.boxes_data if box['name'] != name]
        self.update_box_list()
        self.mark_dirty()

    def start_packing(self):
        # Зчитування даних про контейнер
        try:
            container_width = float(self.container_width_entry.get())
            container_height = float(self.container_height_entry.get())
            container_depth = float(self.container_depth_entry.get())
            container_max_weight = float(self.container_max_weight_entry.get())
        except ValueError:
            messagebox.showerror("Помилка", "Будь ласка, введіть коректні числові значення для контейнера.")
            return
        
        # Створення об'єкту контейнера та ініціалізація оптимізатора
        container = Container(
            width=container_width,
            height=container_height,
            depth=container_depth,
            max_weight=container_max_weight
        )

        optimizer = PackingOptimizer(container)
        # Додавання коробок, зібраних через GUI
        for box in self.boxes_data:
            try:
                item = Item(
                    name=box['name'],
                    width=box['width'],
                    height=box['height'],
                    depth=box['depth'],
                    weight=box['weight'],
                    quantity=box['quantity']
                )
            except Exception as e:
                messagebox.showerror("Помилка", f"Помилка при створенні об'єкта коробки: {str(e)}")
                continue
            optimizer.add_item(item)

        self.start_packing_button.config(state="disabled")
        self.progress['value'] = 0
        self.progress_lbl.config(text="")

        def run():
            # ⬇️ передаємо СВОЮ функцію у pack()
            optimizer.pack(
                progress_cb=lambda done, total: self.progress_q.put((done, total))
            )
            # сигнал про завершення
            self.progress_q.put(("DONE", optimizer))
        self.start_time = time.time()          # ⬅️

        threading.Thread(target=run, daemon=True).start()
        self.after(100, self._poll_progress)  # починаємо слухати чергу

        # Візуалізація результатів – викликаємо через after, щоб не блокувати головний цикл

    def _poll_progress(self):
        try:
            msg = self.progress_q.get_nowait()
        except queue.Empty:
            # Якщо немає нових повідомлень — перевіряємо ще раз через 100 мс
            self.after(100, self._poll_progress)
            return

        # Якщо оптимізатор завершив роботу
        if msg[0] == "DONE":
            _, optimizer = msg

            # 1) Створюємо matplotlib-фігуру, але не відображаємо її в GUI
            fig = optimizer.visualize_packing(show=False)

            # 2) Збираємо дані контейнера й коробок для збереження
            container = {
                "width":      float(self.container_width_entry.get()),
                "height":     float(self.container_height_entry.get()),
                "depth":      float(self.container_depth_entry.get()),
                "max_weight": float(self.container_max_weight_entry.get())
            }
            boxes = self.boxes_data.copy()
            name = self.session_name_entry.get().strip() or f"Сесія {time.strftime('%Y-%m-%d %H:%M:%S')}"

            # 3) Зберігаємо сесію в БД
            session_id = save_session_to_db(name, container, boxes, fig, optimizer.packed_items)
            print(f"[DB] Збережено сесію #{session_id} — «{name}»")

            # 4) Відкриваємо вікно з візуалізацією результату
            self.show_visualization(optimizer)

            # gui.py, у _poll_progress, відразу після виклику self.show_visualization(optimizer)
            self.packed = True
            self.visualization_open = True
            self.dirty = False
            # кнопка вже була вимкнена перед стартом, лишаємо її в такому стані

            # Повертаємось — більше не читаємо з черги
            return

        # Інакше — це оновлення прогресу
        done, total = msg
        elapsed = time.time() - self.start_time

        self.progress['maximum'] = total
        self.progress['value']   = done
        percent = done / total * 100
        self.progress_lbl.config(
            text=f"{done}/{total} ({percent:.0f} %)   {elapsed:.1f} с"
        )

        # Запланувати наступну перевірку
        self.after(100, self._poll_progress)

    def show_visualization(self, optimizer: PackingOptimizer):
        # Одне єдине вікно візуалізації
        win = tk.Toplevel(self)
        win.title("3D Візуалізація пакування")
        win.protocol("WM_DELETE_WINDOW", lambda: self.on_viz_close(win))

        # Панель керування зліва
        controls = tk.Frame(win)
        controls.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        util_lbl = tk.Label(
            controls,
            text=f"Використано простору: {optimizer.space_utilization:.2f}%"
        )
        util_lbl.pack(anchor='w', pady=(0, 10))

        failed_btn = tk.Button(
            controls,
            text="Показати непридатні коробки",
            command=lambda: self.show_failed_modal(optimizer.failed_items)
        )
        failed_btn.pack(anchor='w', pady=(0, 10))

        # Створюємо 3D-фігуру
        fig = plt.Figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        ax.format_coord = lambda x, y: ""
        optimizer._draw_container(ax)

        artists_by_name: dict[str, list] = {}
        for item in optimizer.packed_items:
            x, y, z = item['position']
            w, d, h = item['size']
            color = item['color']
            verts = [
                [x, y, z], [x, y + d, z], [x + w, y + d, z], [x + w, y, z],
                [x, y, z + h], [x, y + d, z + h], [x + w, y + d, z + h], [x + w, y, z + h]
            ]
            faces = [
                [verts[0], verts[1], verts[2], verts[3]],
                [verts[4], verts[5], verts[6], verts[7]],
                [verts[0], verts[1], verts[5], verts[4]],
                [verts[2], verts[3], verts[7], verts[6]],
                [verts[0], verts[3], verts[7], verts[4]],
                [verts[1], verts[2], verts[6], verts[5]],
            ]
            poly = Poly3DCollection(faces, facecolors=[(*color, 0.5)],
                                    edgecolors='k', linewidths=0.5, alpha=0.5)
            ax.add_collection3d(poly)
            artists_by_name.setdefault(item['name'], []).append(poly)

            center = np.array([x + w/2, y + d/2, z + h/2])
            txt = ax.text(
                center[0], center[1], center[2],
                item['name'], fontsize=8, ha='center', va='center'
            )
            artists_by_name[item['name']].append(txt)

        ax.set_xlim(0, optimizer.container.width)
        ax.set_ylim(0, optimizer.container.depth)
        ax.set_zlim(0, optimizer.container.height)
        try:
            ax.set_box_aspect((
                optimizer.container.width,
                optimizer.container.depth,
                optimizer.container.height
            ))
        except AttributeError:
            pass

        # Поміщаємо canvas у те саме вікно
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.RIGHT, fill='both', expand=True)

        toolbar = NavigationToolbar2Tk(canvas, win)
        toolbar.update()
        toolbar.pack(side=tk.BOTTOM, fill='x')

        # Чекбокси для керування видимістю
        var_by_name: dict[str, tk.BooleanVar] = {}
        all_var = tk.BooleanVar(value=True)

        def toggle_all():
            state = all_var.get()
            for name, var in var_by_name.items():
                var.set(state)
                for art in artists_by_name[name]:
                    art.set_visible(state)
            canvas.draw()

        cb_all = tk.Checkbutton(
            controls, text="Усі коробки", variable=all_var, command=toggle_all
        )
        cb_all.pack(anchor='w', pady=(10, 10))

        for name in artists_by_name:
            var = tk.BooleanVar(value=True)
            var_by_name[name] = var
            def make_cb(n, v):
                return lambda: (
                    [art.set_visible(v.get()) for art in artists_by_name[n]],
                    canvas.draw()
                )
            cb = tk.Checkbutton(
                controls, text=name, variable=var,
                command=make_cb(name, var)
            )
            cb.pack(anchor='w')

    def show_failed_modal(self, failed_items: dict):
        modal = tk.Toplevel(self)
        modal.title("Непридатні коробки")
        modal.grab_set()  # робимо модальним

        frame = ttk.Frame(modal)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        # Treeview для failed_items
        tree = ttk.Treeview(
            frame,
            columns=("name", "qty"),
            show="headings",
            height=10
        )
        tree.heading("name", text="Назва коробки")
        tree.heading("qty", text="К-ть")
        tree.column("name", width=200, anchor='w')
        tree.column("qty", width=60, anchor='center')

        for name, cnt in failed_items.items():
            tree.insert("", "end", values=(name, cnt))

        vsb = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')

        # Кнопка для закриття модального вікна
        close_btn = tk.Button(modal, text="Закрити", command=modal.destroy)
        close_btn.pack(pady=5)

    def mark_dirty(self):
        # якщо ще не було жодного пакування — нічого не робимо
        if not self.packed:
            return
        self.dirty = True
        # якщо 3D-вікно вже закрите — одразу розблоковуємо кнопку
        if not self.visualization_open:
            self.start_packing_button.config(state="normal")

if __name__ == "__main__":
    app = Application()
    app.mainloop()