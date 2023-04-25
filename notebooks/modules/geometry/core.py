from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional, SupportsFloat, Union
from enum import auto, Enum
import math


EPSILON: float = 1e-9    # Chosen by testing currently implemented algorithms with the visualisation tool.


class Orientation(Enum):
    LEFT = auto()
    RIGHT = auto()
    BETWEEN = auto()
    BEFORE_SOURCE = auto()
    BEHIND_TARGET = auto()


class GeometricObject(ABC):     # TODO: Rename, move and export this.
    @abstractmethod
    def points(self) -> Iterator[Point]:
        pass

    def animation_events(self) -> Iterator[AnimationEvent]:
        return (AppendEvent(point) for point in self.points())


class Point:
    def __init__(self, x: SupportsFloat, y: SupportsFloat):
        self._x = float(x)
        self._y = float(y)

    ## Properties

    @property
    def x(self) -> float:
        return self._x

    @property
    def y(self) -> float:
        return self._y

    ## Operations

    def distance(self, other: Point) -> float:
        return math.sqrt((self._x - other._x)**2 + (self._y - other._y)**2)

    def dot(self, other: Point) -> float:
        return self._x * other._x + self._y * other._y

    def perp_dot(self, other: Point) -> float:
        return self._x * other._y - self._y * other._x

    def orientation(self, source: Point, target: Point, epsilon: float = EPSILON) -> Orientation:
        if source == target:
            raise ValueError("Source and target need to be two different points.")

        self_direction = self - source
        target_direction = target - source
        signed_area = self_direction.perp_dot(target_direction)

        if signed_area < -epsilon:
            return Orientation.LEFT
        elif signed_area > epsilon:
            return Orientation.RIGHT
        else:
            a = self_direction.dot(target_direction) / target_direction.dot(target_direction)
            # We don't need epsilon here, because the calculation of `a` ensures that
            # `a == 0.0` if `self == source`, whereas `a == 1.0` if `self == target`.
            if a < 0.0:
                return Orientation.BEFORE_SOURCE
            elif a > 1.0:
                return Orientation.BEHIND_TARGET
            else:
                return Orientation.BETWEEN

    ## Magic methods
        
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Point):
            return NotImplemented

        return self._x == other._x and self._y == other._y
    
    def __hash__(self) -> int:
        return hash((self._x, self._y))
    
    def __repr__(self) -> str:
        return f"({self._x}, {self._y})"

    def __add__(self, other: Any) -> Point:
        if not isinstance(other, Point):
            return NotImplemented

        return Point(self._x + other._x, self._y + other._y)

    def __sub__(self, other: Any) -> Point:
        if not isinstance(other, Point):
            return NotImplemented

        return Point(self._x - other._x, self._y - other._y)

    def __rmul__(self, other: Any) -> Point:
        try:
            x = float(other * self._x)
            y = float(other * self._y)
        except Exception:
            return NotImplemented

        return Point(x, y)

    def __round__(self, ndigits: Optional[int] = None) -> Point:
        return Point(round(self._x, ndigits), round(self._y, ndigits))

class PointReference(Point):    # TODO: Make this a generic type for points with attributes.
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

    @property
    def _x(self) -> float:
        return self.point.x

    @property
    def _y(self) -> float:
        return self.point.y


class LineSegment:
    def __init__(self, p: Point, q: Point):
        if p == q:
            raise ValueError("A line segment needs two different endpoints.")
        if p.y > q.y or (p.y == q.y and p.x < q.x):
            self._upper = p
            self._lower = q
        else:
            self._upper = q
            self._lower = p

    ## Properties

    @property
    def upper(self) -> Point:
        return self._upper

    @property
    def lower(self) -> Point:
        return self._lower

    ## Operation(s)

    def intersection(self, other: LineSegment, epsilon: float = EPSILON) -> Union[Point, LineSegment, None]:
        self_direction = self._upper - self._lower
        other_direction = other._upper - other._lower
        lower_offset = other._lower - self._lower
        signed_area_sd_od = self_direction.perp_dot(other_direction)
        signed_area_lo_od = lower_offset.perp_dot(other_direction)
        signed_area_lo_sd = lower_offset.perp_dot(self_direction)

        if abs(signed_area_sd_od) > epsilon:
            a = signed_area_lo_od / signed_area_sd_od
            b = signed_area_lo_sd / signed_area_sd_od
            if -epsilon <= a <= 1.0 + epsilon and -epsilon <= b <= 1.0 + epsilon:
                return self._lower + a * self_direction
            else:
                return None

        # Check both signed areas to ensure consistency and increase robustness.
        if abs(signed_area_lo_od) <= epsilon or abs(signed_area_lo_sd) <= epsilon:
            self_direction_dot = self_direction.dot(self_direction)
            upper_offset = other._upper - self._lower
            a_lower = lower_offset.dot(self_direction) / self_direction_dot
            a_upper = upper_offset.dot(self_direction) / self_direction_dot

            # The inner min/max operations aren't needed in theory, because `a_lower < a_upper`
            # should always hold. However, inaccuracies might somehow invalidate that.
            a_lower_clipped = max(0.0, min(a_lower, a_upper))
            a_upper_clipped = min(1.0, max(a_lower, a_upper))
            upper = self._lower + a_upper_clipped * self_direction
            if a_lower_clipped == a_upper_clipped:
                return upper
            elif a_lower_clipped < a_upper_clipped:
                lower = self._lower + a_lower_clipped * self_direction
                return LineSegment(upper, lower)
            else:
                return None

        return None

    ## Magic methods

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, LineSegment):
            return NotImplemented

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
