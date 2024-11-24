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
    shape: Optional[np.ndarray] = field(default=None)

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
        self.grid_size = 5
        self.space_matrix = np.zeros((
            int(container.width // self.grid_size),
            int(container.depth // self.grid_size),
            int(container.height // self.grid_size)
        ), dtype=int)
        self.current_weight = 0

    def add_item(self, item: Item):
        self.items.extend([item] * item.quantity)

    def check_dimensions(self, size: Tuple[float, float, float]) -> bool:
        w, h, d = size
        return (w <= self.container.width and 
                h <= self.container.height and 
                d <= self.container.depth)

    def get_possible_rotations(self, item: Item) -> List[np.ndarray]:
        if not item.rotatable:
            if item.shape is not None:
                return [item.shape]
            else:
                shape = np.ones((
                    int(item.height // self.grid_size),
                    int(item.width // self.grid_size),
                    int(item.depth // self.grid_size)
                ), dtype=int)
                return [shape]
        
        if item.shape is None:
            rotations = list(set(itertools.permutations([item.width, item.height, item.depth])))
            valid_rotations = []
            for r in rotations:
                if self.check_dimensions(r):
                    shape = np.ones((
                        int(r[1] // self.grid_size),
                        int(r[0] // self.grid_size),
                        int(r[2] // self.grid_size)
                    ), dtype=int)
                    valid_rotations.append(shape)
            return valid_rotations
        else:
            unique_rotations = []
            rotations_set = set()
            shape = item.shape
            for axis in ['x', 'y', 'z']:
                for k in range(4):
                    rotated_shape = np.rot90(shape, k=k, axes=self._get_axes(axis))
                    rotated_shape = self._trim_shape(rotated_shape)
                    shape_tuple = tuple(rotated_shape.flatten())
                    if shape_tuple not in rotations_set and self.check_shape_dimensions(rotated_shape, item):
                        rotations_set.add(shape_tuple)
                        unique_rotations.append(rotated_shape.copy())
            return unique_rotations

    def _get_axes(self, axis: str) -> Tuple[int, int]:
        if axis == 'x':
            return (1, 2)
        elif axis == 'y':
            return (0, 2)
        elif axis == 'z':
            return (0, 1)
        else:
            return (0, 1)

    def _trim_shape(self, shape: np.ndarray) -> np.ndarray:
        non_empty = np.any(shape, axis=(0,1))
        shape = shape[:, :, non_empty]
        non_empty = np.any(shape, axis=(0,2))
        shape = shape[:, non_empty, :]
        non_empty = np.any(shape, axis=(1,2))
        shape = shape[non_empty, :, :]
        return shape

    def check_shape_dimensions(self, shape: np.ndarray, item: Item) -> bool:
        shape_dim = shape.shape
        w = shape_dim[1] * self.grid_size
        h = shape_dim[0] * self.grid_size
        d = shape_dim[2] * self.grid_size
        return self.check_dimensions((w, h, d))

    def check_fit(self, pos: Tuple[int, int, int], shape: np.ndarray) -> bool:
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        shape_transposed = shape.transpose(1, 2, 0)
        
        if (x + shape_w > self.space_matrix.shape[0] or
            y + shape_d > self.space_matrix.shape[1] or
            z + shape_h > self.space_matrix.shape[2]):
            return False

        region = self.space_matrix[x:x + shape_w, y:y + shape_d, z:z + shape_h]
        overlap = np.logical_and(region, shape_transposed)
        return not np.any(overlap)

    def has_support(self, pos: Tuple[int, int, int], shape: np.ndarray) -> bool:
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        shape_transposed = shape.transpose(1, 2, 0)
        
        if z == 0:
            return True
        
        support_level = z - 1
        support_area = self.space_matrix[x:x + shape_w, y:y + shape_d, support_level]
        base_shape = shape_transposed[:, :, 0]

        supported = support_area * base_shape
        support_percentage = np.sum(supported) / np.sum(base_shape) if np.sum(base_shape) > 0 else 0
        return support_percentage >= 0.3

    def _calculate_contact(self, pos: Tuple[int, int, int], shape: np.ndarray) -> int:
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        shape_transposed = shape.transpose(1, 2, 0)
        contact = 0

        if z == 0:
            contact += np.sum(shape_transposed[:, :, 0])
        else:
            support = self.space_matrix[x:x + shape_w, y:y + shape_d, z - 1]
            contact += np.sum(support * shape_transposed[:, :, 0])

        if x > 0:
            front_space = self.space_matrix[x - 1, y:y + shape_d, z:z + shape_h]
            front_shape = shape_transposed[:, :, 0]
            if front_space.shape == front_shape.shape:
                contact += np.sum(front_space * front_shape)
            else:
                min_w = min(front_space.shape[0], front_shape.shape[0])
                min_h = min(front_space.shape[1], front_shape.shape[1])
                contact += np.sum(front_space[:min_w, :min_h] * front_shape[:min_w, :min_h])

        if x + shape_w < self.space_matrix.shape[0]:
            back_space = self.space_matrix[x + shape_w, y:y + shape_d, z:z + shape_h]
            back_shape = shape_transposed[:, :, -1]
            if back_space.shape == back_shape.shape:
                contact += np.sum(back_space * back_shape)
            else:
                min_w = min(back_space.shape[0], back_shape.shape[0])
                min_h = min(back_space.shape[1], back_shape.shape[1])
                contact += np.sum(back_space[:min_w, :min_h] * back_shape[:min_w, :min_h])

        if y > 0:
            left_space = self.space_matrix[x:x + shape_w, y - 1, z:z + shape_h]
            left_shape = shape_transposed[:, 0, :]
            if left_space.shape == left_shape.shape:
                contact += np.sum(left_space * left_shape)
            else:
                min_w = min(left_space.shape[0], left_shape.shape[0])
                min_h = min(left_space.shape[1], left_shape.shape[1])
                contact += np.sum(left_space[:min_w, :min_h] * left_shape[:min_w, :min_h])

        if y + shape_d < self.space_matrix.shape[1]:
            right_space = self.space_matrix[x:x + shape_w, y + shape_d, z:z + shape_h]
            right_shape = shape_transposed[:, -1, :]
            if right_space.shape == right_shape.shape:
                contact += np.sum(right_space * right_shape)
            else:
                min_w = min(right_space.shape[0], right_shape.shape[0])
                min_h = min(right_space.shape[1], right_shape.shape[1])
                contact += np.sum(right_space[:min_w, :min_h] * right_shape[:min_w, :min_h])

        return contact

    def check_stability(self, pos: Tuple[int, int, int], shape: np.ndarray) -> bool:
        return self.has_support(pos, shape)

    def find_best_position(self, item: Item) -> Tuple[Optional[Tuple[int, int, int]], Optional[np.ndarray]]:
        best_pos = None
        best_shape = None
        min_z = float('inf')
        max_contact = float('-inf')
        
        rotations = self.get_possible_rotations(item)
        
        for shape in rotations:
            shape_h, shape_w, shape_d = shape.shape
            
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
        x, y, z = pos
        shape_h, shape_w, shape_d = shape.shape
        shape_transposed = shape.transpose(1, 2, 0)

        self.space_matrix[x:x + shape_w, y:y + shape_d, z:z + shape_h] += shape_transposed

        occupied = np.argwhere(shape_transposed > 0)
        min_i, min_j, min_k = occupied.min(axis=0)
        max_i, max_j, max_k = occupied.max(axis=0)

        box_position = (x + min_i, y + min_j, z + min_k)
        box_size = (max_i - min_i + 1, max_j - min_j + 1, max_k - min_k + 1)

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
        failed_items = defaultdict(int)
        
        self.items.sort(key=lambda x: (
            -(x.width * x.height * x.depth if x.shape is None else np.sum(x.shape) * (self.grid_size ** 3)),
            -(x.width * x.depth if x.shape is None else x.shape.shape[1] * x.shape.shape[2] * (self.grid_size ** 2)),
            -x.weight
        ))
        
        total_volume = 0
        container_volume = self.container.width * self.container.height * self.container.depth

        start_time = time.time()
        
        for item in self.items:
            if self.current_weight + item.weight > self.container.max_weight:
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
                failed_items[item.name] += 1
        
        end_time = time.time()
        duration = end_time - start_time

        self.space_utilization = (total_volume / container_volume) * 100

        final_weight = self.current_weight

        packed_summary = defaultdict(lambda: {'count': 0, 'total_weight': 0.0})
        for packed_item in self.packed_items:
            packed_summary[packed_item['name']]['count'] += 1
            packed_summary[packed_item['name']]['total_weight'] += packed_item['weight']

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
        return {
            'packed_items': self.packed_items,
            'space_utilization': self.space_utilization
        }

    def visualize_packing(self):
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        self._draw_container(ax)
        
        for item in self.packed_items:
            self._draw_item(ax, item)
        
        ax.set_xlabel('Ширина')
        ax.set_ylabel('Глибина')
        ax.set_zlabel('Висота')
        
        max_dim = max(self.container.width, self.container.height, self.container.depth)
        ax.set_xlim(0, max_dim)
        ax.set_ylim(0, max_dim)
        ax.set_zlim(0, max_dim)
        
        plt.title(f'3D Візуалізація Пакування\nВикористання простору: {self.space_utilization:.2f}%')
        plt.show()

    def _draw_container(self, ax):
        vertices = [
            [0, 0, 0], [0, self.container.depth, 0], 
            [self.container.width, self.container.depth, 0], [self.container.width, 0, 0],
            [0, 0, self.container.height], [0, self.container.depth, self.container.height],
            [self.container.width, self.container.depth, self.container.height], 
            [self.container.width, 0, self.container.height]
        ]
        
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],
            [vertices[4], vertices[5], vertices[6], vertices[7]],
            [vertices[0], vertices[1], vertices[5], vertices[4]],
            [vertices[2], vertices[3], vertices[7], vertices[6]],
            [vertices[0], vertices[3], vertices[7], vertices[4]],
            [vertices[1], vertices[2], vertices[6], vertices[5]]
        ]
        
        container_edges = []
        for face in faces:
            for i in range(len(face)):
                edge = [face[i], face[(i + 1) % len(face)]]
                container_edges.append(edge)
        container_edges = np.array(container_edges)
        
        line_collection = Line3DCollection(container_edges, colors='gray', linewidths=1, linestyles='dashed')
        ax.add_collection3d(line_collection)

    def _draw_item(self, ax, item):
        x, y, z = item['position']
        w, d, h = item['size']

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

        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],
            [vertices[4], vertices[5], vertices[6], vertices[7]],
            [vertices[0], vertices[1], vertices[5], vertices[4]],
            [vertices[2], vertices[3], vertices[7], vertices[6]],
            [vertices[0], vertices[3], vertices[7], vertices[4]],
            [vertices[1], vertices[2], vertices[6], vertices[5]]
        ]

        color = item['color']

        face_collection = Poly3DCollection(faces, 
                                           facecolors=[(*color, 0.5)],
                                           edgecolors='k', 
                                           linewidths=0.5, 
                                           alpha=0.5)
        ax.add_collection3d(face_collection)

        center = np.array([x + w/2, y + d/2, z + h/2])
        ax.text(center[0], center[1], center[2], item['name'], 
                fontsize=8, ha='center', va='center')

def create_l_shape(grid_size: int) -> np.ndarray:
    shape = np.zeros((2, 2, 2), dtype=int)
    shape[0, 0, 0] = 1
    shape[0, 1, 0] = 1
    shape[1, 0, 0] = 1
    shape[1, 0, 1] = 1
    return shape

def main():
    result_file = 'result.txt'
    open(result_file, 'w').close()
    
    container = Container(width=100, height=100, depth=100, max_weight=2000)
    optimizer = PackingOptimizer(container)
    
    items = [
        Item("MediumBox", 30, 30, 30, 20, quantity=0),
        Item("SmallBox", 20, 20, 20, 10, quantity=0),
        Item("LongBox", 60, 20, 20, 15, quantity=0),
        Item("FlatBox", 40, 40, 10, 8, quantity=0),
        Item("FlatBox", 10, 20, 10, 3, quantity=0),
        Item("TallBox", 20, 50, 20, 12, quantity=0),
    ]
    
    l_shape = create_l_shape(grid_size=optimizer.grid_size)
    items.append(
        Item(
            name="LShapeBox",
            width=l_shape.shape[2] * optimizer.grid_size,
            height=l_shape.shape[0] * optimizer.grid_size,
            depth=l_shape.shape[1] * optimizer.grid_size,
            weight=10,
            quantity=400,
            rotatable=True,
            shape=l_shape
        )
    )
    
    for item in items:
        optimizer.add_item(item)
    
    utilization = optimizer.pack()
    results = optimizer.get_packing_results()
    
    optimizer.visualize_packing()

if __name__ == "__main__":
    main()
