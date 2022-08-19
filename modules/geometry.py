from enum import Enum, auto
import math
import numpy as np

from typing import Iterable, Union, Any
from abc import ABC, abstractmethod


class Orientation(Enum):
    LEFT = auto()
    RIGHT = auto()
    BEHIND_SOURCE = auto()
    BETWEEN = auto()
    BEHIND_TARGET = auto()


class Point:
    def __init__(self, x, y):
        #self.x = x
        #self.y = y
        self._coords = np.array([x, y])

    @property
    def x(self):
        return self._coords[0]
    
    @property
    def y(self):
        return self._coords[1]
        
    def __eq__(self, other) -> bool:
        return self.x == other.x and self.y == other.y
    
    def __hash__(self) -> int:
        return hash((self.x, self.y))
    
    def __repr__(self) -> str:
        return f"Point({self.x}, {self.y})"
    
    #def distance(self, other: 'Point') -> float:
    #    return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def orientation(self, source: 'Point', target: 'Point') -> Orientation:
        if source == target:
            raise ValueError("Line (segment) needs two different points")
        val = (target.x - source.x) * (self.y - source.y) - (target.y - source.y) * (self.x - source.x)
        if val > 0.0:
            return Orientation.LEFT
        elif val < 0.0:
            return Orientation.RIGHT
        else:
            if source.x != target.x:
                param = (self.x - source.x) / (target.x - source.x)
            else:
                param = (self.y - source.y) / (target.y - source.y)
            if param < 0.0:
                return Orientation.BEHIND_SOURCE
            elif param > 1.0:
                return Orientation.BEHIND_TARGET
            else:
                return Orientation.BETWEEN

class PointReference(Point):
    def __init__(self, container: list[Point], position: int):
        self._container = container
        self._position = position
        
    def get_point(self) -> Point:
        return self._container[self._position]
    
    @property
    def x(self):
        return self.get_point().x
    
    @property
    def y(self):
        return self.get_point().y

    def get_position(self) -> int:
        return self._position
    
    def is_in_container(self, container: list[Point]) -> bool:
        return container is self._container


class Polygon:
    def __init__(self, points: Iterable[Point] = []):
        self.points: list[Point] = []
        self.events: list[Event] = []
        self._previously_drawn_container = None
        for point in points:
            self.append(point, draw_container = False)

    def append(self, point: Point, draw_container: bool = True):
        self.points.append(point)

        if draw_container and isinstance(point, PointReference):
            if point._container is self._previously_drawn_container:
                draw_container = False
            else:
                self._previously_drawn_container = point._container

        if self.events and isinstance(self.events[-1], PopEvent):           # For GiftWrapping.
            self.events[-1] = SetEvent(-1, point, draw_container)
        else:
            self.events.append(AppendEvent(point, draw_container))

    def pop(self) -> Point:
        point = self.points.pop()
        self.events.append(PopEvent())
        return point

    def animate(self, point: Point):
        self.append(point)
        self.pop()

    def __repr__(self) -> str:
        return self.points.__repr__()

    def __len__(self) -> int:
        return len(self.points)

    def __getitem__(self, key) -> Union[Point, 'Polygon']:
        # This implementation is a hack, but it works for Graham Scan.
        if isinstance(key, slice):
            if key.step is not None and key.step != 1:
                raise ValueError("Polygon doesn't accept slice keys with a step different from 1.")
            result = Polygon()
            result.points = self.points[key]
            result.events = self.events[:]
            return result
        return self.points[key]

    def __delitem__(self, key):
        if not isinstance(key, int) or key >= 0:
            # This constraint enables an easy implementation of __add__(). TODO: Can probably be changed now.
            raise ValueError("Polygon only accepts a negative integer as a deletion key.")
        del self.points[key]
        self.events.append(DeleteEvent(key))

    def __add__(self, other: 'Polygon') -> 'Polygon':
        result = Polygon()
        result.points = self.points + other.points
        result.events = self.events + other.events
        return result


# TODO: Generalise 'background_points'.
class Event(ABC):
    @abstractmethod
    def execute_on(self, points: list[Point], background_points: list[Point]):
        pass

class AppendEvent(Event):
    def __init__(self, point: Point, draw_container: bool):
        self.point = point
        self.draw_container = draw_container

    def execute_on(self, points: list[Point], background_points: list[Point]):
        points.append(self.point)
        if self.draw_container and isinstance(self.point, PointReference):
            background_points.extend(self.point._container)

class PopEvent(Event):
    def execute_on(self, points: list[Point], background_points: list[Point]):
        points.pop()

class SetEvent(Event):
    def __init__(self, key, point, draw_container: bool):
        self.key = key
        self.point = point
        self.draw_container = draw_container

    def execute_on(self, points: list[Point], background_points: list[Point]):
        points[self.key] = self.point
        if self.draw_container and isinstance(self.point, PointReference):
            background_points.extend(self.point._container)

class DeleteEvent(Event):
    def __init__(self, key):
        self.key = key

    def execute_on(self, points: list[Point], background_points: list[Point]):
        del points[self.key]




class LineSegment:
    def __init__(self, p: Point, q: Point):
        if p == q:
            raise ValueError("Line (segment) needs two different points")
        if p.y > q.y or (p.y == q.y and p.x < q.x):     # TODO: maybe make is_upper method or similar (see [CG, p. 24] for order)
            self.upper = p
            self.lower = q
        else:
            self.upper = q
            self.lower = p

    def intersection(self, other: 'LineSegment') -> Union[None, Point, 'LineSegment']:
        a = self.upper      # TODO: maybe implement add, subtract, ... on Point
        b = self.lower
        c = other.upper
        d = other.lower
        if (a.x - b.x) * (c.y - d.y) == (c.x - d.x) * (a.y - b.y):  # Line segments are parallel. TODO: Check for overlap. (-> degenerate case)
            return None
        elif a.y == b.y:
            point = other.get_point_at_same_height(a)
            if a.x <= point.x <= b.x:
                return point
            else:
                return None
        else:
            coefficent = (c.x - d.x) - (b.x - a.x) * (c.y - d.y) / (b.y - a.y)
            t = ((c.x - a.x) - (b.x - a.x) * (c.y - a.y) / (b.y - a.y)) / coefficent
            #s = (c.y - a.y) / (b.y - a.y) - t * (c.y - d.y) / (b.y - a.y)
            s = ((c.y - a.y) - t * (c.y - d.y)) / (b.y - a.y)
            if 0 <= s <= 1 and 0 <= t <= 1:
                #p1 = Point((1 - s) * a.x + s * b.x, (1 - s) * a.y + s * b.y)
                #p2 = Point((1 - t) * c.x + t * d.x, (1 - t) * c.y + t * d.y)
                p1 = Point(a.x + s * (b.x - a.x), a.y + s * (b.y - a.y))
                p2 = Point(c.x + t * (d.x - c.x), c.y + t * (d.y - c.y))
                #print(f"{p1} vs {p2}")                                   # TODO: p1 and p2 can differ... (-> not robust)
                return p2
            else:
                return None

    def get_point_at_same_height(self, point: Point) -> Point:          # TODO: Add checks?
        scale = (point.y - self.lower.y) / (self.upper.y - self.lower.y)
        x = self.lower.x + scale * (self.upper.x - self.lower.x)
        return Point(x, point.y)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LineSegment):
            raise TypeError("Need LineSegment")
        return self.upper == other.upper and self.lower == other.lower

    def __hash__(self) -> int:
        return hash((self.upper, self.lower))

    def __repr__(self) -> str:
        return f"{self.upper}--{self.lower}"
