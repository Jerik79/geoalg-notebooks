from abc import ABC, abstractmethod
import time
from typing import Callable, Generic, Optional, TypeVar

from geometry import GeometricPrimitive, Point, LineSegment
from .drawing import DrawingMode, LineSegmentsMode, PointsMode

import numpy as np


T = TypeVar("T")

Algorithm = Callable[[T], GeometricPrimitive]

class InstanceHandle(ABC, Generic[T]):
    _instance: T
    _drawing_mode: DrawingMode

    @abstractmethod
    def add_point(self, point: Point) -> bool:
        pass

    def clear(self):
        self._instance.clear()

    def __len__(self) -> int:
        return len(self._instance)

    def run_algorithm(self, algorithm: Algorithm[T]) -> tuple[GeometricPrimitive, float]:
        start_time = time.time()
        algorithm_output = algorithm(self._instance)
        end_time = time.time()
        return algorithm_output, 1000 * (end_time - start_time)

    @property
    def drawing_mode(self) -> DrawingMode:
        return self._drawing_mode

    def default_random_point_number(self) -> int:
        return 250

    def get_random_coordinate(self, maximum: int) -> float:
        return np.random.uniform(0, maximum)

class PointSetInstance(InstanceHandle[set[Point]]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        self._instance: set[Point] = set()
        self._drawing_mode = drawing_mode
        if self._drawing_mode is None:
            self._drawing_mode = PointsMode()

    def add_point(self, point: Point) -> bool:
        if point in self._instance:
            return False
        self._instance.add(point)
        return True

    def get_random_coordinate(self, maximum: int) -> float:
        return float(np.clip(np.random.normal(0.5 * maximum, 0.15 * maximum), 0, maximum))

class LineSegmentSetInstance(InstanceHandle[set[LineSegment]]):
    def __init__(self, drawing_mode: Optional[DrawingMode] = None):
        self._instance: set[LineSegment] = set()
        self._cached_point: Optional[Point] = None
        self._drawing_mode = drawing_mode
        if self._drawing_mode is None:
            self._drawing_mode = LineSegmentsMode(draw_vertices = True)

    def add_point(self, point: Point) -> bool:
        if self._cached_point is None:
            self._cached_point = point
            return True
        line_segment = LineSegment(self._cached_point, point)
        if line_segment in self._instance:
            return False
        self._instance.add(line_segment)
        self._cached_point = None
        return True
