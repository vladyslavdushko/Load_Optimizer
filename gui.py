import os
os.environ["TCL_LIBRARY"] = "/opt/homebrew/opt/tcl-tk/lib/tcl8.6"
os.environ["TK_LIBRARY"] = "/opt/homebrew/Cellar/tcl-tk/9.0.1/lib/tk9.0"
import tkinter as tk
from tkinter import messagebox
from optimizer import Container, Item, PackingOptimizer
import matplotlib
matplotlib.use('MacOSX')
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
            background="#ffffe0",  # світло-жовтий фон
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
        self.config_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        self.input_frame = tk.Frame(self.config_frame)
        self.input_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        self.box_list_frame = tk.LabelFrame(self.config_frame, text="Додані коробки", padx=10, pady=10)
        self.box_list_frame.grid(row=0, column=1, sticky="nsew")
        
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
        
        # Кнопка для запуску процесу упаковки – вона завжди активна, якщо хоча б одна коробка додана
        self.start_packing_button = tk.Button(
            self.input_frame, 
            text="Почати упаковку", 
            command=self.start_packing,
            state="disabled"  # спочатку вимкнена, поки не додано хоча б одну коробку
        )
        self.start_packing_button.grid(row=13, column=0, columnspan=2, pady=10)
        
        # Оновлення правого блоку зі списком коробок
        self.update_box_list()

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
        # Очищення фрейму зі списком коробок
        for widget in self.box_list_frame.winfo_children():
            widget.destroy()

        if not self.summary_box:
            tk.Label(self.box_list_frame, text="Немає доданих коробок").pack()
            return

        # Для кожного типу коробок створюємо віджет-мітку з інформацією і прив'язуємо tooltip
        for box_name, data in self.summary_box.items():
            text = f"{box_name}: {data['count']} шт."
            lbl = tk.Label(self.box_list_frame, text=text, anchor="w")
            lbl.pack(fill="x", padx=5, pady=2)
            tooltip_text = (
                f"Ширина: {data['width']} мм\n"
                f"Висота: {data['height']} мм\n"
                f"Глибина: {data['depth']} мм\n"
                f"Вага: {data['weight']} кг"
            )
            ToolTip(lbl, tooltip_text)

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
        
        # Запуск алгоритму упаковки
        utilization = optimizer.pack()
        messagebox.showinfo("Результати", f"Успішність пакування: {utilization:.2f}%")
        
        # Візуалізація результатів – викликаємо через after, щоб не блокувати головний цикл
        self.after(100, optimizer.visualize_packing)

if __name__ == "__main__":
    app = Application()
    app.mainloop()
