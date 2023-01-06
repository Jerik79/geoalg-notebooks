from abc import ABC, abstractmethod
import copy
from itertools import chain
import time
from typing import Callable, Generic, Optional, TypeVar

from ..geometry.core import GeometricObject, LineSegment, Point
from ..geometry.objects import DoublyConnectedPolygon
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
        start_time = time.time()
        algorithm_output = algorithm(self._instance)
        end_time = time.time()
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

    def get_random_point(self, max_x: float, max_y: float) -> Point:
        x = np.random.uniform(0.05 * max_x, 0.95 * max_x)
        y = np.random.uniform(0.05 * max_y, 0.95 * max_y)
        return Point(x, y)


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

    def get_random_point(self, max_x: float, max_y: float) -> Point:
        x = float(np.clip(np.random.normal(0.5 * max_x, 0.15 * max_x), 0.05 * max_x, 0.95 * max_x))
        y = float(np.clip(np.random.normal(0.5 * max_y, 0.15 * max_y), 0.05 * max_y, 0.95 * max_y))
        return Point(x, y)


class LineSegmentSetInstance(InstanceHandle[set[LineSegment]]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        if drawing_mode is None:
            drawing_mode = LineSegmentsMode(endpoint_radius = 3)
        super().__init__(set(), drawing_mode)
        self._cached_point = None
        self._cached_random_point = None

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
        self._cached_random_point = None

    def size(self) -> int:
        return len(self._instance)

    @staticmethod
    def extract_points_from_raw_instance(instance: set[LineSegment]) -> list[Point]:
        return list(chain.from_iterable(segment.points() for segment in instance))

    @property
    def default_number_of_random_points(self) -> int:
        return 500

    def get_random_point(self, max_x: float, max_y: float) -> Point:
        if self._cached_random_point is None:
            self._cached_random_point = super().get_random_point(max_x, max_y)
            return self._cached_random_point
        scale = np.random.uniform(0.01, 0.05)
        x = float(np.clip(np.random.normal(self._cached_random_point.x, scale * max_x), 0.05 * max_x, 0.95 * max_x))
        y = float(np.clip(np.random.normal(self._cached_random_point.y, scale * max_y), 0.05 * max_y, 0.95 * max_y))
        self._cached_random_point = None
        return Point(x, y)


class SimplePolygonInstance(InstanceHandle[DoublyConnectedPolygon]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        if drawing_mode is None:
            drawing_mode = PolygonMode(draw_interior = False)
        super().__init__(DoublyConnectedPolygon(), drawing_mode)

    def run_algorithm(self, algorithm: Algorithm[DoublyConnectedPolygon]) -> tuple[GeometricObject, float]:
        copied_instance = copy.deepcopy(self._instance)
        self._instance.close()
        result = super().run_algorithm(algorithm)
        self._instance = copied_instance
        return result

    def add_point(self, point: Point) -> bool:
        if not self._instance.check_simplicity(point):
            return False
        self._instance.add_vertex(point)
        return True

    def clear(self):
        self._instance.clear()

    def size(self) -> int:
        return len(self._instance)

    @staticmethod
    def extract_points_from_raw_instance(instance: DoublyConnectedPolygon) -> list[Point]:
        return list(vertex._point for vertex in instance._vertices())

    @property
    def default_number_of_random_points(self) -> int:
        return 25

    # TODO: Implement get_random_point().
