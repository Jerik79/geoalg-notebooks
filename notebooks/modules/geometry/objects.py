from __future__ import annotations
from collections import OrderedDict
from typing import Any, Iterable, Iterator, Union

from .core import *


class PointSequence(GeometricObject):
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

    def clear(self):
        self._points.clear()
        self._animation_events.append(ClearEvent())

    def animate(self, point: Point):
        self._animation_events.append(AppendEvent(point))
        self._animation_events.append(PopEvent())

    def reset_animations(self):
        self._animation_events = list(super().animation_events())

    def __repr__(self) -> str:
        return self._points.__repr__()

    def __add__(self, other: Any) -> PointSequence:
        if not isinstance(other, PointSequence):
            raise TypeError("Parameter 'other' needs to be of type 'PointSequence'.")
        result = PointSequence()
        result._points = self._points + other._points
        result._animation_events = self._animation_events + other._animation_events
        return result

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, key: Any) -> Union[Point, PointSequence]:
        if isinstance(key, int):
            return self._points[key]
        elif isinstance(key, slice) and (key.step is None or key.step == 1):
            # This implementation is a hack, but it works for Graham Scan.
            result = PointSequence()
            result._points = self._points[key]
            result._animation_events = self._animation_events[:]
            return result
        else:
            raise ValueError("Parameter 'key' needs to be an integer or a slice with step 1.")

    def __delitem__(self, key: Any):
        if not isinstance(key, int) or key >= 0:
            # This constraint enables an easy implementation of __add__(). TODO: Can probably be changed now.
            raise ValueError("Parameter 'key' needs to be a negative integer.")
        del self._points[key]
        self._animation_events.append(DeleteEvent(key))


# TODO: Actually make this generic. For that, an Updater like for binary trees is needed. Maybe share type vars and aliases?
class PointSequenceDict(GeometricObject):
    def __init__(self):
        self._intersections: OrderedDict[Point, set[LineSegment]] = OrderedDict()
        self._animation_events: list[AnimationEvent] = []

    def points(self) -> Iterator[Point]:
        return iter(self._intersections)

    def animation_events(self) -> Iterator[AnimationEvent]:
        return iter(self._animation_events)

    def add(self, intersection_point: Point, line_segments: Iterable[LineSegment]):
        rounded_point = round(intersection_point, 5)
        containing_segments: set[LineSegment] = self._intersections.setdefault(rounded_point, set())
        if not containing_segments:
            self._animation_events.append(AppendEvent(rounded_point))
        containing_segments.update(line_segments)

    def animate(self, point: Point):
        self._animation_events.append(AppendEvent(point))
        self._animation_events.append(PopEvent())

    def __repr__(self) -> str:
        return "\n".join(f"{point}: {segments}" for point, segments in self._intersections.items())
