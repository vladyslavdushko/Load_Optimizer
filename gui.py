import os
os.environ["TCL_LIBRARY"] = "/opt/homebrew/opt/tcl-tk/lib/tcl8.6"
os.environ["TK_LIBRARY"] = "/opt/homebrew/Cellar/tcl-tk/9.0.1/lib/tk9.0"
import time
import tkinter as tk
import threading, queue
from tkinter import messagebox, filedialog
from optimizer import Container, Item, PackingOptimizer
import matplotlib
import platform
from tkinter import ttk
import json, os

if platform.system() == 'Darwin':
    matplotlib.use('MacOSX')
else:
    matplotlib.use('TkAgg')

import matplotlib.pyplot as plt

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
        self.geometry("800x600")
        
        self.container_data = None
        # self.boxes_data – список словників з даними коробок
        self.boxes_data = []  
        # summary_box – словник для зведеної інформації по коробкам {назва: {count, width, height, depth, weight}}
        self.summary_box = {}
        
        self.show_welcome_screen()
        self.progress_q = queue.Queue()
        
    def show_welcome_screen(self):
        # Вітальне вікно з кнопкою для створення нового завантаження
        self.welcome_frame = tk.Frame(self)
        self.welcome_frame.pack(expand=True, fill='both')
        
        welcome_label = tk.Label(self.welcome_frame, text="Ласкаво просимо до 3D Bin Packing", font=("Arial", 16))
        welcome_label.pack(pady=20)
        
        new_load_button = tk.Button(
            self.welcome_frame, 
            text="Створити нове завантаження", 
            font=("Arial", 14), 
            command=self.show_configuration_screen
        )
        new_load_button.pack(pady=10)
    
    def show_configuration_screen(self):
        # Видаляємо вітальне вікно
        self.welcome_frame.destroy()
        
        # Створюємо контейнерний фрейм з двома колонками: зліва – введення даних, справа – список доданих коробок
        self.config_frame = tk.Frame(self)
        self.config_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        self.input_frame = tk.Frame(self.config_frame)
        self.input_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        self.box_list_frame = tk.LabelFrame(self.config_frame, text="Додані коробки", padx=5, pady=5)
        self.box_list_frame.grid(row=0, column=1)
        
        self.box_tree = ttk.Treeview(
            self.box_list_frame, columns=("qty", "w", "h", "d", "weight"),
            show = "headings", height = 5
        )
        self.box_tree.heading("qty", text="К-ть")
        self.box_tree.heading("w", text="W")
        self.box_tree.heading("h", text="H")
        self.box_tree.heading("d", text="D")
        self.box_tree.heading("weight", text="Кг")
        self.box_tree.pack(fill="both")

        edit_btn = tk.Button(self.box_list_frame, text="Змінити кількість",
                     command=self.edit_selected_box)
        edit_btn.pack(pady=2)

        # Налаштування розтягування колонок
        self.config_frame.columnconfigure(0, weight=3)
        self.config_frame.columnconfigure(1, weight=1)
        
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

    def update_box_list(self):
        # очистити
        for row in self.box_tree.get_children():
            self.box_tree.delete(row)

        for name, data in self.summary_box.items():
            self.box_tree.insert(
                "", "end", iid=name,   # iid == назва коробки
                values=(data["count"], data["width"], data["height"],
                        data["depth"], data["weight"])
            )

    def edit_selected_box(self):
        selected = self.box_tree.focus()
        if not selected:
            messagebox.showinfo("Інфо", "Спершу виберіть коробку у списку.")
            return

        name = selected
        current_qty = self.summary_box[name]["count"]

        # невелике вікно вводу
        win = tk.Toplevel(self)
        win.title(f"Змінити кількість – {name}")
        tk.Label(win, text="Нова кількість:").grid(row=0, column=0, padx=5, pady=5)
        qty_entry = tk.Entry(win)
        qty_entry.insert(0, str(current_qty))
        qty_entry.grid(row=0, column=1, padx=5, pady=5)

        def apply():
            try:
                new_qty = int(qty_entry.get())
                if new_qty < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Помилка", "Введіть невід’ємне ціле число.")
                return

            diff = new_qty - current_qty
            self.summary_box[name]["count"] = new_qty

            # синхронізуємо self.boxes_data --------------
            if diff > 0:            # треба ДОДАТИ копії
                for b in self.boxes_data:
                    if b["name"] == name:
                        b["quantity"] += diff
                        break
            else:                   # треба ЗМЕНШИТИ
                for b in self.boxes_data:
                    if b["name"] == name:
                        b["quantity"] = max(0, b["quantity"] + diff)
                        break
            # якщо кількість стала 0 – прибираємо запис
            if new_qty == 0:
                self.boxes_data = [b for b in self.boxes_data if b["name"] != name]
                del self.summary_box[name]

            self.update_box_list()
            win.destroy()

            # якщо списки порожні – вимикаємо кнопку «Почати упаковку»
            if not self.boxes_data:
                self.start_packing_button.config(state="disabled")

        tk.Button(win, text="OK", command=apply).grid(row=1, column=0, columnspan=2, pady=5)


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
            self.after(100, self._poll_progress)
            return

        # повідомлення
        if msg[0] == "DONE":
            _, optimizer = msg
            total_time = time.time() - self.start_time
            self.progress_lbl.config(text=f"Завершено за {total_time:.1f} с")

            self.progress['value'] = self.progress['maximum']  # 100%

            # знову активуємо кнопку
            self.start_packing_button.config(state="normal")

            utilization = optimizer.space_utilization
            messagebox.showinfo("Результати", f"Успішність пакування: {utilization:.2f}%")

            # викликаємо візуалізацію після невеликої затримки,
            # щоб вікно встигло оновитись
            self.after(100, optimizer.visualize_packing)
        else:  # отримали (done, total)
            done, total = msg
            elapsed = time.time() - self.start_time   # ⬅️ секунд від початку

            self.progress['maximum'] = total
            self.progress['value']   = done
            percent = done / total * 100
            self.progress_lbl.config(
                text=f"{done}/{total}  ({percent:.0f} %)   {elapsed:.1f} с"
            )

            self.after(100, self._poll_progress)


if __name__ == "__main__":
    app = Application()
    app.mainloop()
