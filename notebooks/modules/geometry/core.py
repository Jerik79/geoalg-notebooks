from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, SupportsFloat, Union
from enum import auto, Enum
import math


EPSILON: float = 1e-9      # This seems to be a good value, at least for our standard coordinate range (0 to 400).

def set_epsilon(epsilon: float):
    if not math.isfinite(epsilon) or epsilon < 0.0:
        return ValueError("The epsilon value must be a finite positive number.")
    global EPSILON
    EPSILON = epsilon

def reset_epsilon():
    global EPSILON
    EPSILON = 1e-9


class Orientation(Enum):
    LEFT = auto()
    RIGHT = auto()
    BEHIND_SOURCE = auto()
    BETWEEN = auto()
    BEHIND_TARGET = auto()


class GeometricObject(ABC):
    @abstractmethod
    def points(self) -> Iterator[Point]:
        pass

    def animation_events(self) -> Iterator[AnimationEvent]:
        return (AppendEvent(point) for point in self.points())


class Point(GeometricObject):
    def __init__(self, x: SupportsFloat, y: SupportsFloat):
        self.x = float(x)
        self.y = float(y)

    def points(self) -> Iterator[Point]:
        yield self

    def distance(self, other: Point) -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def dot(self, other: Point) -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: Point) -> float:
        return self.x * other.y - other.x * self.y

    def orientation(self, source: Point, target: Point) -> Orientation:
        if source == target:
            raise ValueError("Source and target need to be two different points.")
        direction = target - source
        offset = self - source
        cross = offset.cross(direction)
        if abs(cross) <= EPSILON:
            t = offset.dot(direction) / direction.dot(direction)
            if t < 0.0:
                return Orientation.BEHIND_SOURCE
            elif t > 1.0:
                return Orientation.BEHIND_TARGET
            else:
                return Orientation.BETWEEN
        elif cross < 0.0:
            return Orientation.LEFT
        else:
            return Orientation.RIGHT
        
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Point):
            return False
        return self.x == other.x and self.y == other.y
    
    def __hash__(self) -> int:
        return hash((self.x, self.y))
    
    def __repr__(self) -> str:
        return f"({self.x}, {self.y})"

    def __add__(self, other: Any) -> Point:
        if not isinstance(other, Point):
            raise TypeError("Parameter 'other' needs to be of type 'Point'.")
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Any) -> Point:
        if not isinstance(other, Point):
            raise TypeError("Parameter 'other' needs to be of type 'Point'.")
        return Point(self.x - other.x, self.y - other.y)

    def __rmul__(self, other: Any) -> Point:
        if not isinstance(other, float) and not isinstance(other, int):
            raise TypeError("Parameter 'other' needs to be of type 'float' or 'int'.")
        return Point(other * self.x, other * self.y)

    def __round__(self, ndigits: Optional[int] = None) -> Point:
        return Point(round(self.x, ndigits), round(self.y, ndigits))

class PointReference(Point):
    def __init__(self, container: list[Point], position: int):
        self._container = container
        self._position = position

    @property
    def container(self) -> list[Point]:
        return self._container

    @property
    def position(self) -> int:
        return self._position

    @property
    def point(self) -> Point:
        return self._container[self._position]

    @property
    def x(self) -> float:
        return self.point.x

    @property
    def y(self) -> float:
        return self.point.y


class LineSegment(GeometricObject):
    def __init__(self, p: Point, q: Point):
        if p == q:
            raise ValueError("A line segment needs two different endpoints.")
        if p.y > q.y or (p.y == q.y and p.x < q.x):
            self.upper = p
            self.lower = q
        else:
            self.upper = q
            self.lower = p

    def points(self) -> Iterator[Point]:
        yield self.upper
        yield self.lower

    def intersection(self, other: LineSegment) -> Union[None, Point, LineSegment]:
        self_direction = self.upper - self.lower
        other_direction = other.upper - other.lower
        directions_cross = self_direction.cross(other_direction)
        offset = other.lower - self.lower

        if abs(directions_cross) > EPSILON:
            t = offset.cross(other_direction) / directions_cross
            u = offset.cross(self_direction) / directions_cross
            if -EPSILON <= t <= 1.0 + EPSILON and -EPSILON <= u <= 1.0 + EPSILON:
                return self.lower + t * self_direction
        elif abs(offset.cross(self_direction)) <= EPSILON:
            self_direction_dot = self_direction.dot(self_direction)
            t0 = offset.dot(self_direction) / self_direction_dot
            t1 = t0 + other_direction.dot(self_direction) / self_direction_dot
            t_min, t_max = max(0.0, min(t0, t1)), min(1.0, max(t0, t1))
            if t_min == t_max:
                return self.lower + t_min * self_direction
            elif t_min < t_max:
                return LineSegment(self.lower + t_min * self_direction, self.lower + t_max * self_direction)

        return None

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LineSegment):
            return False
        return self.upper == other.upper and self.lower == other.lower

    def __hash__(self) -> int:
        return hash((self.upper, self.lower))

    def __repr__(self) -> str:
        return f"{self.upper}--{self.lower}"


class AnimationEvent(ABC):      # TODO: Maybe use an Enum instead...
    @abstractmethod
    def execute_on(self, points: list[Point]):
        pass

class AppendEvent(AnimationEvent):
    def __init__(self, point: Point):
        self.point = point

    def execute_on(self, points: list[Point]):
        points.append(self.point)

class PopEvent(AnimationEvent):
    def execute_on(self, points: list[Point]):
        points.pop()

class SetEvent(AnimationEvent):
    def __init__(self, key: int, point: Point):
        self.key = key
        self.point = point

    def execute_on(self, points: list[Point]):
        points[self.key] = self.point

class DeleteEvent(AnimationEvent):
    def __init__(self, key: int):
        self.key = key

    def execute_on(self, points: list[Point]):
        del points[self.key]

class ClearEvent(AnimationEvent):
    def execute_on(self, points: list[Point]):
        points.clear()
