from abc import ABC, abstractmethod
from itertools import chain
import time
from typing import Callable, Generic, Optional, TypeVar

from ..geometry.core import GeometricObject, LineSegment, Point
from ..data_structures import DoublyConnectedSimplePolygon
from .drawing import DrawingMode, LineSegmentsMode, PointsMode, PolygonMode

import numpy as np


I = TypeVar("I")

Algorithm = Callable[[I], GeometricObject]

class InstanceHandle(ABC, Generic[I]):
    def __init__(self, instance: I, drawing_mode: DrawingMode):
        self._instance = instance
        self._drawing_mode = drawing_mode

    @property
    def drawing_mode(self) -> DrawingMode:
        return self._drawing_mode

    def run_algorithm(self, algorithm: Algorithm[I]) -> tuple[GeometricObject, float]:
        instance_points = self.extract_points_from_raw_instance(self._instance)

        start_time = time.perf_counter()
        algorithm_output = algorithm(self._instance)
        end_time = time.perf_counter()

        self.clear()
        for point in instance_points:
            self.add_point(point)

        return algorithm_output, 1000 * (end_time - start_time)

    @abstractmethod
    def add_point(self, point: Point) -> bool:
        pass

    @abstractmethod
    def clear(self):
        pass

    @abstractmethod
    def size(self) -> int:
        pass

    @staticmethod
    @abstractmethod
    def extract_points_from_raw_instance(instance: I) -> list[Point]:
        pass

    @property
    @abstractmethod
    def default_number_of_random_points(self) -> int:
        pass

    def generate_random_points(self, max_x: float, max_y: float, number: int) -> list[Point]:
        x_values = np.random.uniform(0.05 * max_x, 0.95 * max_x, number)
        y_values = np.random.uniform(0.05 * max_y, 0.95 * max_y, number)
        return [Point(x, y) for x, y  in zip(x_values, y_values)]


class PointSetInstance(InstanceHandle[set[Point]]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        if drawing_mode is None:
            drawing_mode = PointsMode()
        super().__init__(set(), drawing_mode)

    def add_point(self, point: Point) -> bool:
        if point in self._instance:
            return False
        self._instance.add(point)

        return True

    def clear(self):
        self._instance.clear()

    def size(self) -> int:
        return len(self._instance)

    @staticmethod
    def extract_points_from_raw_instance(instance: set[Point]) -> list[Point]:
        return list(instance)

    @property
    def default_number_of_random_points(self) -> int:
        return 250

    def generate_random_points(self, max_x: float, max_y: float, number: int) -> list[Point]:
        x_values = np.clip(np.random.normal(0.5 * max_x, 0.15 * max_x, number), 0.05 * max_x, 0.95 * max_x)
        y_values = np.clip(np.random.normal(0.5 * max_y, 0.15 * max_y, number), 0.05 * max_y, 0.95 * max_y)
        return [Point(x, y) for x, y in zip(x_values, y_values)]


class LineSegmentSetInstance(InstanceHandle[set[LineSegment]]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        if drawing_mode is None:
            drawing_mode = LineSegmentsMode(vertex_radius = 3)
        super().__init__(set(), drawing_mode)
        self._cached_point: Optional[Point] = None

    def add_point(self, point: Point) -> bool:
        if self._cached_point is None:
            self._cached_point = point
            return True
        elif self._cached_point == point:
            return False

        line_segment = LineSegment(self._cached_point, point)
        if line_segment in self._instance:
            return False
        self._instance.add(line_segment)
        self._cached_point = None

        return True

    def clear(self):
        self._instance.clear()
        self._cached_point = None

    def size(self) -> int:
        return len(self._instance)

    @staticmethod
    def extract_points_from_raw_instance(instance: set[LineSegment]) -> list[Point]:
        return list(chain.from_iterable((segment.upper, segment.lower) for segment in instance))

    @property
    def default_number_of_random_points(self) -> int:
        return 500

    def generate_random_points(self, max_x: float, max_y: float, number: int) -> list[Point]:
        points: list[Point] = []
        for point in super().generate_random_points(max_x, max_y, number // 2):
            points.append(point)
            scale = np.random.uniform(0.01, 0.05)
            x = np.clip(np.random.normal(point.x, scale * max_x), 0.05 * max_x, 0.95 * max_x)
            y = np.clip(np.random.normal(point.y, scale * max_y), 0.05 * max_y, 0.95 * max_y)
            points.append(Point(x, y))

        if number % 2 == 1:
            points.extend(super().generate_random_points(max_x, max_y, 1))

        return points


class SimplePolygonInstance(InstanceHandle[DoublyConnectedSimplePolygon]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        if drawing_mode is None:
            drawing_mode = PolygonMode(mark_closing_edge = True, draw_interior = False, vertex_radius = 3)
        super().__init__(DoublyConnectedSimplePolygon(), drawing_mode)

    def add_point(self, point: Point) -> bool:
        try:
            self._instance.add_vertex(point)
        except Exception:
            return False

        return True

    def clear(self):
        self._instance.clear()

    def size(self) -> int:
        return len(self._instance)

    @staticmethod
    def extract_points_from_raw_instance(instance: DoublyConnectedSimplePolygon) -> list[Point]:
        return [vertex.point for vertex in instance.vertices()]

    @property
    def default_number_of_random_points(self) -> int:
        return 100

    def generate_random_points(self, max_x: float, max_y: float, number: int) -> list[Point]:
        while True:
            points = super().generate_random_points(max_x, max_y, number)

            try:
                polygon = DoublyConnectedSimplePolygon.try_from_unordered_points(points)
            except Exception:
                continue

            return self.extract_points_from_raw_instance(polygon)
