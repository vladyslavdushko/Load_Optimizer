import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
import random
import itertools
from collections import defaultdict
import time

@dataclass
class Item:
    name: str
    width: float
    height: float
    depth: float
    weight: float
    quantity: int = 1
    rotatable: bool = True
    shape: Optional[np.ndarray] = field(default=None)  # 3D numpy array representing the shape

@dataclass
class Container:
    width: float
    height: float
    depth: float
    max_weight: float

class PackingOptimizer:
    def __init__(self, container: Container):
        self.container = container
        self.items = []
        self.packed_items = []
        self.space_utilization = 0.0
        self.grid_size = 5  # Розмір сітки
        # Визначаємо space_matrix з осями (width, depth, height)
        self.space_matrix = np.zeros((
            int(container.width // self.grid_size),
            int(container.depth // self.grid_size),
            int(container.height // self.grid_size)
        ), dtype=int)
        self.current_weight = 0

    def add_item(self, item: Item):
        """Додати предмет до списку для пакування"""
        self.items.extend([item] * item.quantity)

    def check_dimensions(self, size: Tuple[float, float, float]) -> bool:
        """Перевірка чи не перевищують розміри предмета розміри контейнера"""
        w, h, d = size
        return (w <= self.container.width and 
                h <= self.container.height and 
                d <= self.container.depth)

    def get_possible_rotations(self, item: Item) -> List[np.ndarray]:
        """Отримати всі можливі обертання предмета"""
        if not item.rotatable:
            if item.shape is not None:
                return [item.shape]
            else:
                # Стандартна коробка як numpy масив
                shape = np.ones((
                    int(item.height // self.grid_size),
                    int(item.width // self.grid_size),
                    int(item.depth // self.grid_size)
                ), dtype=int)
                return [shape]
        
        if item.shape is None:
            # Стандартна коробка: генеруємо обертання як розміри
            rotations = list(set(itertools.permutations([item.width, item.height, item.depth])))
            valid_rotations = []
            for r in rotations:
                if self.check_dimensions(r):
                    # Створюємо numpy масив для кожної допустимої обертання
                    shape = np.ones((
                        int(r[1] // self.grid_size),  # height
                        int(r[0] // self.grid_size),  # width
                        int(r[2] // self.grid_size)   # depth
                    ), dtype=int)
                    valid_rotations.append(shape)
            return valid_rotations
        else:
            # Нестандартна форма: обертаємо форму в 90-градусних кроках
            unique_rotations = []
            rotations_set = set()
            shape = item.shape
            for axis in ['x', 'y', 'z']:
                for k in range(4):  # 0°, 90°, 180°, 270°
                    rotated_shape = np.rot90(shape, k=k, axes=self._get_axes(axis))
                    rotated_shape = self._trim_shape(rotated_shape)
                    shape_tuple = tuple(rotated_shape.flatten())
                    if shape_tuple not in rotations_set and self.check_shape_dimensions(rotated_shape, item):
                        rotations_set.add(shape_tuple)
                        unique_rotations.append(rotated_shape.copy())
            return unique_rotations

    def _get_axes(self, axis: str) -> Tuple[int, int]:
        """Допоміжний метод для визначення осей обертання"""
        if axis == 'x':
            return (1, 2)  # Rotate around x: y and z
        elif axis == 'y':
            return (0, 2)  # Rotate around y: x and z
        elif axis == 'z':
            return (0, 1)  # Rotate around z: x and y
        else:
            return (0, 1)

    def _trim_shape(self, shape: np.ndarray) -> np.ndarray:
        """Обрізання зайвих нулів навколо форми"""
        # Видаляємо порожні слайси по кожній осі
        non_empty = np.any(shape, axis=(0,1))  # Видаляємо порожні на осі 2
        shape = shape[:, :, non_empty]
        non_empty = np.any(shape, axis=(0,2))  # Видаляємо порожні на осі 1
        shape = shape[:, non_empty, :]
        non_empty = np.any(shape, axis=(1,2))  # Видаляємо порожні на осі 0
        shape = shape[non_empty, :, :]
        return shape

    def check_shape_dimensions(self, shape: np.ndarray, item: Item) -> bool:
        """Перевірка, чи не перевищує форма розміри контейнера"""
        shape_dim = shape.shape  # (height, width, depth)
        w = shape_dim[1] * self.grid_size
        h = shape_dim[0] * self.grid_size
        d = shape_dim[2] * self.grid_size
        return self.check_dimensions((w, h, d))

    def check_fit(self, pos: Tuple[int, int, int], shape: np.ndarray) -> bool:
        """Перевірити чи поміщається предмет в дану позицію"""
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        # Транспонуємо форму для відповідності space_matrix (width, depth, height)
        shape_transposed = shape.transpose(1, 2, 0)
        
        # Перевірка чи не виходить за межі контейнера
        if (x + shape_w > self.space_matrix.shape[0] or
            y + shape_d > self.space_matrix.shape[1] or
            z + shape_h > self.space_matrix.shape[2]):
            return False

        # Перевірка на перетин з іншими предметами
        region = self.space_matrix[x:x + shape_w, y:y + shape_d, z:z + shape_h]
        overlap = np.logical_and(region, shape_transposed)
        return not np.any(overlap)

    def has_support(self, pos: Tuple[int, int, int], shape: np.ndarray) -> bool:
        """Перевірка опори"""
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        # Транспонуємо форму для відповідності space_matrix (width, depth, height)
        shape_transposed = shape.transpose(1, 2, 0)
        
        if z == 0:
            return True
        
        support_level = z - 1
        # support_area має форму (shape_w, shape_d)
        support_area = self.space_matrix[x:x + shape_w, y:y + shape_d, support_level]
        # base_shape також має форму (shape_w, shape_d)
        base_shape = shape_transposed[:, :, 0]  # Нижня площина предмета
        
        # Перевірка підтримки для кожної колонки бази предмета
        supported = support_area * base_shape
        support_percentage = np.sum(supported) / np.sum(base_shape) if np.sum(base_shape) > 0 else 0
        return support_percentage >= 0.3  # Мінімум 30% опори

    def _calculate_contact(self, pos: Tuple[int, int, int], shape: np.ndarray) -> int:
        """Розрахунок площі контакту з іншими коробками"""
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        # Транспонуємо форму для відповідності space_matrix (width, depth, height)
        shape_transposed = shape.transpose(1, 2, 0)
        contact = 0

        # Контакт знизу
        if z == 0:
            contact += np.sum(shape_transposed[:, :, 0])
        else:
            support = self.space_matrix[x:x + shape_w, y:y + shape_d, z - 1]
            contact += np.sum(support * shape_transposed[:, :, 0])

        # Контакт з передньою стороною (front)
        if x > 0:
            front_space = self.space_matrix[x - 1, y:y + shape_d, z:z + shape_h]
            front_shape = shape_transposed[:, :, 0]  # (width, height)
            # Перевірка відповідності розмірів
            if front_space.shape == front_shape.shape:
                contact += np.sum(front_space * front_shape)
            else:
                min_w = min(front_space.shape[0], front_shape.shape[0])
                min_h = min(front_space.shape[1], front_shape.shape[1])
                contact += np.sum(front_space[:min_w, :min_h] * front_shape[:min_w, :min_h])

        # Контакт з задньою стороною (back)
        if x + shape_w < self.space_matrix.shape[0]:
            back_space = self.space_matrix[x + shape_w, y:y + shape_d, z:z + shape_h]
            back_shape = shape_transposed[:, :, -1]  # (width, height)
            if back_space.shape == back_shape.shape:
                contact += np.sum(back_space * back_shape)
            else:
                min_w = min(back_space.shape[0], back_shape.shape[0])
                min_h = min(back_space.shape[1], back_shape.shape[1])
                contact += np.sum(back_space[:min_w, :min_h] * back_shape[:min_w, :min_h])

        # Контакт з лівою стороною (left)
        if y > 0:
            left_space = self.space_matrix[x:x + shape_w, y - 1, z:z + shape_h]
            left_shape = shape_transposed[:, 0, :]  # (width, height)
            if left_space.shape == left_shape.shape:
                contact += np.sum(left_space * left_shape)
            else:
                min_w = min(left_space.shape[0], left_shape.shape[0])
                min_h = min(left_space.shape[1], left_shape.shape[1])
                contact += np.sum(left_space[:min_w, :min_h] * left_shape[:min_w, :min_h])

        # Контакт з правою стороною (right)
        if y + shape_d < self.space_matrix.shape[1]:
            right_space = self.space_matrix[x:x + shape_w, y + shape_d, z:z + shape_h]
            right_shape = shape_transposed[:, -1, :]  # (width, height)
            if right_space.shape == right_shape.shape:
                contact += np.sum(right_space * right_shape)
            else:
                min_w = min(right_space.shape[0], right_shape.shape[0])
                min_h = min(right_space.shape[1], right_shape.shape[1])
                contact += np.sum(right_space[:min_w, :min_h] * right_shape[:min_w, :min_h])

        # Контакт з верхньою стороною (top) не враховується
        return contact

    def check_stability(self, pos: Tuple[int, int, int], shape: np.ndarray) -> bool:
        """Перевірка стабільності розміщення"""
        return self.has_support(pos, shape)

    def find_best_position(self, item: Item) -> Tuple[Optional[Tuple[int, int, int]], Optional[np.ndarray]]:
        best_pos = None
        best_shape = None
        min_z = float('inf')
        max_contact = float('-inf')
        
        rotations = self.get_possible_rotations(item)
        
        for shape in rotations:
            shape_h, shape_w, shape_d = shape.shape
            
            # Перебираємо позиції знизу вгору
            for z in range(self.space_matrix.shape[2] - shape_h + 1):
                if z > min_z:
                    continue
                for x in range(self.space_matrix.shape[0] - shape_w + 1):
                    for y in range(self.space_matrix.shape[1] - shape_d + 1):
                        pos = (x, y, z)
                        
                        if (self.check_fit(pos, shape) and 
                            self.has_support(pos, shape) and 
                            self.check_stability(pos, shape)):
                            
                            contact = self._calculate_contact(pos, shape)
                            
                            if z < min_z or (z == min_z and contact > max_contact):
                                min_z = z
                                max_contact = contact
                                best_pos = pos
                                best_shape = shape.copy()
        
        return best_pos, best_shape

    def place_item(self, pos: Tuple[int, int, int], item: Item, shape: np.ndarray):
        """Розмістити предмет в контейнері"""
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        # Транспонуємо форму для відповідності space_matrix (width, depth, height)
        shape_transposed = shape.transpose(1, 2, 0)

        # Маркуємо зайняті клітинки
        self.space_matrix[x:x + shape_w, y:y + shape_d, z:z + shape_h] += shape_transposed

        # Визначаємо мінімальні та максимальні координати для коробки
        occupied = np.argwhere(shape_transposed > 0)
        min_i, min_j, min_k = occupied.min(axis=0)
        max_i, max_j, max_k = occupied.max(axis=0)

        box_position = (x + min_i, y + min_j, z + min_k)
        box_size = (max_i - min_i + 1, max_j - min_j + 1, max_k - min_k + 1)

        # Генеруємо випадковий колір для коробки
        color = (random.random(), random.random(), random.random())

        self.packed_items.append({
            'name': item.name,
            'position': (box_position[0] * self.grid_size, box_position[1] * self.grid_size, box_position[2] * self.grid_size),
            'size': (box_size[0] * self.grid_size, box_size[1] * self.grid_size, box_size[2] * self.grid_size),
            'color': color,
            'weight': item.weight
        })
        self.current_weight += item.weight

    def pack(self) -> float:
        # Ініціалізація словника для невдалих розміщень
        failed_items = defaultdict(int)
        
        # Сортуємо за об'ємом, площею основи та вагою
        self.items.sort(key=lambda x: (
            -(x.width * x.height * x.depth if x.shape is None else np.sum(x.shape) * (self.grid_size ** 3)),
            -(x.width * x.depth if x.shape is None else x.shape.shape[1] * x.shape.shape[2] * (self.grid_size ** 2)),
            -x.weight
        ))
        
        total_volume = 0
        container_volume = self.container.width * self.container.height * self.container.depth

        # Вимірювання часу виконання
        start_time = time.time()
        
        for item in self.items:
            if self.current_weight + item.weight > self.container.max_weight:
                # Оновлюємо словник замість виведення повідомлення
                failed_items[item.name] += 1
                continue

            best_pos, best_shape = self.find_best_position(item)
            if best_pos is not None and best_shape is not None:
                self.place_item(best_pos, item, best_shape)
                if item.shape is None:
                    total_volume += item.width * item.height * item.depth
                else:
                    total_volume += np.sum(best_shape) * (self.grid_size ** 3)
            else:
                # Оновлюємо словник замість виведення повідомлення
                failed_items[item.name] += 1
        
        end_time = time.time()
        duration = end_time - start_time

        self.space_utilization = (total_volume / container_volume) * 100

        # Фінальна вага контейнера
        final_weight = self.current_weight

        # Підрахунок успішно розміщених коробок за типами
        packed_summary = defaultdict(lambda: {'count': 0, 'total_weight': 0.0})
        for packed_item in self.packed_items:
            packed_summary[packed_item['name']]['count'] += 1
            packed_summary[packed_item['name']]['total_weight'] += packed_item['weight']

        # Запис результатів у файл
        with open('result.txt', 'a', encoding='utf-8') as f:
            f.write(f"### Результати Пакування\n")
            f.write(f"Розміри контейнера (W x H x D): {self.container.width} x {self.container.height} x {self.container.depth} мм\n")
            f.write(f"Максимальна вага контейнера: {self.container.max_weight} кг\n\n")
            
            f.write(f"Використання простору: {self.space_utilization:.2f}%\n")
            f.write(f"Час виконання: {duration:.2f} секунд\n")
            f.write(f"Фінальна вага контейнера: {final_weight} кг\n\n")
            
            if failed_items:
                f.write("Не вдалося розмістити наступні коробки:\n")
                for name, count in failed_items.items():
                    f.write(f" - {count} коробок типу '{name}'\n")
                f.write("\n")
            
            f.write("Успішно розміщені коробки:\n")
            for name, data in packed_summary.items():
                f.write(f" - {data['count']} коробок типу '{name}', загальна вага: {data['total_weight']} кг\n")
            f.write("\n")
            
            f.write("Деталі успішно розміщених коробок:\n")
            for item in self.packed_items:
                f.write(f"Назва: {item['name']}, Позиція: {item['position']}, Розмір: {item['size']}, Вага: {item['weight']} кг\n")
            f.write("\n" + "="*50 + "\n\n")
        
        return self.space_utilization

    def get_packing_results(self) -> dict:
        """Отримати результати пакування"""
        return {
            'packed_items': self.packed_items,
            'space_utilization': self.space_utilization
        }

    def visualize_packing(self):
        """Візуалізувати результати пакування"""
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Візуалізація контейнера (прозорий)
        self._draw_container(ax)
        
        # Візуалізація кожної розміщеної коробки як обриси та заповнені грані з унікальним кольором
        for item in self.packed_items:
            self._draw_item(ax, item)
        
        # Налаштування відображення
        ax.set_xlabel('Ширина')
        ax.set_ylabel('Глибина')
        ax.set_zlabel('Висота')
        
        # Встановлюємо однаковий масштаб по всіх осях
        max_dim = max(self.container.width, self.container.height, self.container.depth)
        ax.set_xlim(0, max_dim)
        ax.set_ylim(0, max_dim)
        ax.set_zlim(0, max_dim)
        
        plt.title(f'3D Візуалізація Пакування\nВикористання простору: {self.space_utilization:.2f}%')
        plt.show()

    def _draw_container(self, ax):
        """Намалювати контейнер"""
        # Створюємо вершини контейнера
        vertices = [
            [0, 0, 0], [0, self.container.depth, 0], 
            [self.container.width, self.container.depth, 0], [self.container.width, 0, 0],
            [0, 0, self.container.height], [0, self.container.depth, self.container.height],
            [self.container.width, self.container.depth, self.container.height], 
            [self.container.width, 0, self.container.height]
        ]
        
        # Створюємо грані контейнера
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # дно
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # верх
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # перед
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # зад
            [vertices[0], vertices[3], vertices[7], vertices[4]],  # ліво
            [vertices[1], vertices[2], vertices[6], vertices[5]]   # право
        ]
        
        # Збираємо всі лінії граней
        container_edges = []
        for face in faces:
            for i in range(len(face)):
                edge = [face[i], face[(i + 1) % len(face)]]
                container_edges.append(edge)
        container_edges = np.array(container_edges)
        
        # Створюємо Line3DCollection для контейнера
        line_collection = Line3DCollection(container_edges, colors='gray', linewidths=1, linestyles='dashed')
        ax.add_collection3d(line_collection)

    def _draw_item(self, ax, item):
        """Намалювати окрему коробку як обриси та заповнені грані з унікальним кольором та прозорістю"""
        # Отримуємо позицію та розміри коробки
        x, y, z = item['position']
        w, d, h = item['size']  # width, depth, height

        # Визначаємо вершини коробки
        vertices = [
            [x, y, z],
            [x, y + d, z],
            [x + w, y + d, z],
            [x + w, y, z],
            [x, y, z + h],
            [x, y + d, z + h],
            [x + w, y + d, z + h],
            [x + w, y, z + h]
        ]

        # Визначаємо грані коробки
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],  # Дно
            [vertices[4], vertices[5], vertices[6], vertices[7]],  # Верх
            [vertices[0], vertices[1], vertices[5], vertices[4]],  # Передня грань
            [vertices[2], vertices[3], vertices[7], vertices[6]],  # Задня грань
            [vertices[0], vertices[3], vertices[7], vertices[4]],  # Ліва грань
            [vertices[1], vertices[2], vertices[6], vertices[5]]   # Права грань
        ]

        # Отримуємо колір коробки
        color = item['color']

        # Створюємо Poly3DCollection для граней з прозорістю
        face_collection = Poly3DCollection(faces, 
                                           facecolors=[(*color, 0.5)],  # Додаємо альфа-канал для прозорості
                                           edgecolors='k', 
                                           linewidths=0.5, 
                                           alpha=0.5)
        ax.add_collection3d(face_collection)

        # Додаємо підпис до коробки
        center = np.array([x + w/2, y + d/2, z + h/2])
        ax.text(center[0], center[1], center[2], item['name'], 
                fontsize=8, ha='center', va='center')

def create_l_shape(grid_size: int) -> np.ndarray:
    """
    Створює L-подібну форму в 3D-матриці.
    Наприклад, L-подібна форма з розмірами 2x2x2 у сітці 5:
    """
    shape = np.zeros((2, 2, 2), dtype=int)
    shape[0, 0, 0] = 1
    shape[0, 1, 0] = 1
    shape[1, 0, 0] = 1
    shape[1, 0, 1] = 1
    return shape

def main():
    result_file = 'result.txt'
    # Очищуємо файл перед початком тесту
    open(result_file, 'w').close()
    
    # Ініціалізуємо контейнер з розмірами 200x200x200 мм та максимальною вагою 5000 кг
    # (Збільшили максимально допустиму вагу для подвоєної кількості вантажів)
    container = Container(width=100, height=100, depth=100, max_weight=2000)
    optimizer = PackingOptimizer(container)
    
    # Створюємо вантажі (подвоєні кількості)
    items = [
        Item("MediumBox", 30, 30, 30, 20, quantity=20),    # Подвоєна кількість (14 -> 28)
        Item("SmallBox", 20, 20, 20, 10, quantity=30),    # Подвоєна кількість (100 -> 200)
        Item("LongBox", 60, 20, 20, 15, quantity=10),      # Подвоєна кількість (20 -> 40)
        Item("FlatBox", 40, 40, 10, 8, quantity=20),      # Подвоєна кількість (90 -> 180)
        Item("FlatBox", 10, 20, 10, 3, quantity=10),      # Подвоєна кількість (90 -> 180)
        Item("TallBox", 20, 50, 20, 12, quantity=10),      # Подвоєна кількість (10 -> 20)
    ]
    
    # Додаємо нестандартну L-подібну коробку (подвоєна кількість)
    l_shape = create_l_shape(grid_size=optimizer.grid_size)
    items.append(
        Item(
            name="LShapeBox",
            width=l_shape.shape[2] * optimizer.grid_size,  # depth
            height=l_shape.shape[0] * optimizer.grid_size,  # height
            depth=l_shape.shape[1] * optimizer.grid_size,  # width
            weight=10,
            quantity=4,  # Подвоєна кількість (20 -> 40)
            rotatable=True,
            shape=l_shape
        )
    )
    
    # Додаємо всі вантажі до оптимізатора
    for item in items:
        optimizer.add_item(item)
    
    # Виконуємо пакування
    utilization = optimizer.pack()
    results = optimizer.get_packing_results()
    
    # Запис результатів у файл вже зроблено у методі pack()
    
    # Візуалізація результатів
    optimizer.visualize_packing()

if __name__ == "__main__":
    main()
