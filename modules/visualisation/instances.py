from abc import ABC, abstractmethod
from typing import Callable, Generic, Optional, TypeVar
from itertools import chain
import time

from geometry import GeometricPrimitive, Point, LineSegment
from .drawing import DrawingMode, LineSegmentsMode, PointsMode

import numpy as np


T = TypeVar("T")

Algorithm = Callable[[T], GeometricPrimitive]

class InstanceHandle(ABC, Generic[T]):
    def __init__(self, instance: T, drawing_mode: DrawingMode):
        self._instance = instance
        self._drawing_mode = drawing_mode

    def run_algorithm(self, algorithm: Algorithm[T]) -> tuple[GeometricPrimitive, float]:
        start_time = time.time()
        algorithm_output = algorithm(self._instance)
        end_time = time.time()
        return algorithm_output, 1000 * (end_time - start_time)

    @abstractmethod
    def add_point(self, point: Point) -> bool:
        pass

    def clear(self):
        self._instance.clear()

    def __len__(self) -> int:
        return len(self._instance)

    @staticmethod
    def extract_points_from_raw_instance(instance: T) -> list[Point]:
        return list(chain.from_iterable(element.points() for element in instance))

    @property
    def drawing_mode(self) -> DrawingMode:
        return self._drawing_mode

    @property
    def default_number_of_random_points(self) -> int:
        return 250

    def get_random_coordinate(self, maximum: int) -> float:
        return np.random.uniform(0.05 * maximum, 0.95 * maximum)


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

    def get_random_coordinate(self, maximum: int) -> float:
        return float(np.clip(np.random.normal(0.5 * maximum, 0.15 * maximum), 0.05 * maximum, 0.95 * maximum))


class LineSegmentSetInstance(InstanceHandle[set[LineSegment]]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        if drawing_mode is None:
            drawing_mode = LineSegmentsMode(draw_vertices = True)
        super().__init__(set(), drawing_mode)
        self._cached_point = None

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

    @property
    def default_number_of_random_points(self) -> int:
        return 100
