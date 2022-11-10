from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Iterator, Union, Any
from enum import Enum, auto
from collections import OrderedDict
import math


EPSILON = 1e-10         # This seems to be a good value for our standard coordinate range (0 to 400).


class Orientation(Enum):
    LEFT = auto()
    RIGHT = auto()
    BEHIND_SOURCE = auto()
    BETWEEN = auto()
    BEHIND_TARGET = auto()


class GeometricPrimitive(ABC):
    @abstractmethod
    def points(self) -> Iterator[Point]:
        pass

    def animation_events(self) -> Iterator[AnimationEvent]:
        return (AppendEvent(point) for point in self.points())


class Point(GeometricPrimitive):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

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
        if abs(cross) < EPSILON:
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


class LineSegment(GeometricPrimitive):
    def __init__(self, p: Point, q: Point):
        if p == q:
            raise ValueError("LineSegment needs two different endpoints.")
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

        if abs(directions_cross) >= EPSILON:
            t = offset.cross(other_direction) / directions_cross
            u = offset.cross(self_direction) / directions_cross
            if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
                return self.lower + t * self_direction
        elif abs(offset.cross(self_direction)) < EPSILON:
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


from visualisation.drawing import AnimationEvent, AppendEvent, PopEvent, DeleteEvent


class Polygon(GeometricPrimitive):
    def __init__(self, points: Iterable[Point] = []):
        self._points: list[Point] = []
        self._animation_events: list[AnimationEvent] = []
        for point in points:
            self.append(point)

    def points(self) -> Iterator[Point]:
        return iter(self._points)

    def animation_events(self) -> Iterator[AnimationEvent]:
        return iter(self._animation_events)

    def append(self, point: Point):
        self._points.append(point)
        self._animation_events.append(AppendEvent(point))

    def pop(self) -> Point:
        point = self._points.pop()
        self._animation_events.append(PopEvent())
        return point

    def animate(self, point: Point):
        self._animation_events.append(AppendEvent(point))
        self._animation_events.append(PopEvent())

    def __repr__(self) -> str:
        return self._points.__repr__()

    def __add__(self, other: Polygon) -> Polygon:
        result = Polygon()
        result._points = self._points + other._points
        result._animation_events = self._animation_events + other._animation_events
        return result

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, key) -> Union[Point, Polygon]:
        # This implementation is a hack, but it works for Graham Scan.
        if isinstance(key, slice):
            if key.step is not None and key.step != 1:
                raise ValueError("Polygon doesn't accept slice keys with a step different from 1.")
            result = Polygon()
            result._points = self._points[key]
            result._animation_events = self._animation_events[:]
            return result
        return self._points[key]

    def __delitem__(self, key):
        if not isinstance(key, int) or key >= 0:
            # This constraint enables an easy implementation of __add__(). TODO: Can probably be changed now.
            raise ValueError("Polygon only accepts a negative integer as a deletion key.")
        del self._points[key]
        self._animation_events.append(DeleteEvent(key))


class Intersections(GeometricPrimitive):
    def __init__(self):
        self._intersections: OrderedDict[Point, set[LineSegment]] = OrderedDict()
        self._animation_events: list[AnimationEvent] = []

    def points(self) -> Iterator[Point]:
        return iter(self._intersections)

    def animation_events(self) -> Iterator[AnimationEvent]:
        return iter(self._animation_events)

    def add(self, intersection_point: Point, line_segments: Iterable[LineSegment]):
        point_segments = self._intersections.setdefault(intersection_point, set())
        for line_segment in line_segments:
            point_segments.add(line_segment)
        self._animation_events.append(AppendEvent(intersection_point))

    def animate(self, point: Point):
        self._animation_events.append(AppendEvent(point))
        self._animation_events.append(PopEvent())

    def __repr__(self) -> str:
        return "\n".join(f"{point}: {segments}" for point, segments in self._intersections.items())
