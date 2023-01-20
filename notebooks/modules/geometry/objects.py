from __future__ import annotations
from collections import OrderedDict
import copy
from itertools import chain
from typing import Any, Iterable, Iterator, Optional, Union

from .core import *


class Polygon(GeometricObject):
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

    def __add__(self, other: Any) -> Polygon:
        if not isinstance(other, Polygon):
            raise TypeError("Parameter 'other' needs to be of type 'Polygon'.")
        result = Polygon()
        result._points = self._points + other._points
        result._animation_events = self._animation_events + other._animation_events
        return result

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, key: Any) -> Union[Point, Polygon]:
        if isinstance(key, int):
            return self._points[key]
        elif isinstance(key, slice) and (key.step is None or key.step == 1):
            # This implementation is a hack, but it works for Graham Scan.
            result = Polygon()
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


class Intersections(GeometricObject):
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


class DoublyConnectedSimplePolygon(GeometricObject):
    def __init__(self):
        self.clear()

    def clear(self):
        self._topmost_vertex: Optional[Vertex] = None
        self._closing_edge: Optional[HalfEdge] = None
        self._is_reversed: bool = False
        self._has_diagonals: bool = False
        self._number_of_vertices: int = 0

    @property
    def topmost_vertex(self) -> Optional[Vertex]:
        return self._topmost_vertex

    def _vertices(self) -> Iterator[Vertex]:
        if self._closing_edge is None:
            return ()

        yield self._closing_edge.destination
        edge = self._closing_edge._next if self._is_reversed else self._closing_edge.destination._edge
        while edge is not self._closing_edge:
            yield edge.destination
            edge = edge._next if self._is_reversed else edge.destination._edge

    def points(self) -> Iterator[Point]:    # TODO: This is not that useful since it's targeted towards LineSegmentsMode.
        for vertex in self._vertices():
            incident_edge = vertex._edge._prev._twin
            while incident_edge is not vertex._edge and incident_edge._prev._twin is not vertex._edge:
                yield vertex._point
                yield incident_edge.destination._point
                incident_edge = incident_edge._prev._twin

    def animation_events(self) -> Iterator[AnimationEvent]:
        pass

    def is_simple(self, final_vertex_point: Optional[Point] = None) -> bool:
        if self._has_diagonals or self._number_of_vertices + int(final_vertex_point is not None) < 3:
            return False

        point_iterator = chain(
            map(lambda vertex: vertex._point, self._vertices()),
            (final_vertex_point or self._closing_edge.destination._point,)
        )

        line_segments: list[LineSegment] = []
        point = next(point_iterator, None)
        next_point = next(point_iterator, None)
        while next_point is not None:
            if point == next_point:
                return False
            line_segments.append(LineSegment(point, next_point))
            point = next_point
            next_point = next(point_iterator, None)

        if final_vertex_point is None or self._number_of_vertices == 2:
            if isinstance(line_segments[-1].intersection(line_segments[0]), LineSegment):
                return False
        else:
            if line_segments[-1].intersection(line_segments[0]) is not None:
                return False

        for segment in line_segments[1:-2]:
            if line_segments[-1].intersection(segment) is not None:
                return False

        return not isinstance(line_segments[-1].intersection(line_segments[-2]), LineSegment)

    def add_vertex(self, point: Point) -> Optional[Vertex]:
        if (self._number_of_vertices == 1 and point == self._topmost_vertex._point) or \
        (self._number_of_vertices >= 2 and not self.is_simple(point)):
            return None

        vertex = Vertex(point)
        if self._number_of_vertices == 0:
            self._topmost_vertex = vertex
            self._closing_edge = vertex._edge
        else:
            if vertex.y > self._topmost_vertex.y or (vertex.y == self._topmost_vertex.y and \
            vertex.x < self._topmost_vertex.x):
                self._topmost_vertex = vertex
            self._setup_edges_for_new_vertex(vertex)

        self._number_of_vertices += 1
        if self._number_of_vertices >= 3:
            topmost_orientation = self._topmost_vertex.point.orientation(
                self._topmost_vertex._edge._prev._origin._point,
                self._topmost_vertex._edge._next._origin._point
            )
            if topmost_orientation is not Orientation.RIGHT:
                self._reverse_orientation()

        return vertex

    def _setup_edges_for_new_vertex(self, vertex: Vertex):
        old_closing_edge = self._closing_edge
        old_closing_edge_twin = self._closing_edge._twin
        if self._number_of_vertices == 2:
            old_closing_edge = copy.copy(old_closing_edge)
            old_closing_edge_twin = copy.copy(old_closing_edge_twin)
            old_closing_edge._origin._edge = old_closing_edge
            old_closing_edge._set_prev(self._closing_edge._twin)
            old_closing_edge_twin._set_prev(self._closing_edge)

        closing_edge, converse_edge = vertex._edge, HalfEdge(vertex)
        if self._is_reversed:
            closing_edge, converse_edge = converse_edge, closing_edge
        converse_edge._set_twin(old_closing_edge)
        closing_edge._set_twin(old_closing_edge_twin)
        converse_edge._set_next(old_closing_edge_twin._next)
        closing_edge._set_next(old_closing_edge._next)
        converse_edge._set_prev(old_closing_edge_twin)
        closing_edge._set_prev(old_closing_edge)

        self._closing_edge = closing_edge

    def _reverse_orientation(self):
        self._topmost_vertex._edge = self._topmost_vertex._edge._prev._twin
        vertex = self._topmost_vertex._edge.destination
        while vertex is not self._topmost_vertex:
            vertex._edge = vertex._edge._prev._twin
            vertex = vertex._edge.destination

        self._is_reversed = not self._is_reversed

    def add_diagonal(self, connection_edge1: HalfEdge, connection_edge2: HalfEdge) -> Optional[HalfEdge]:
        """The given connection edges need to bound the same incident face, because otherwise invariants of the
        data structure will be violated. This isn't checked, so that the operation can run in constant time."""
        vertex1 = connection_edge1._origin
        vertex2 = connection_edge2._origin
        if vertex1 is vertex2 or vertex1._edge.destination is vertex2 or vertex2._edge.destination is vertex1:
            return None

        diagonal1 = HalfEdge(vertex1)
        diagonal2 = HalfEdge(vertex2)
        diagonal1._set_twin(diagonal2)
        diagonal1._set_prev(connection_edge1._prev)
        diagonal2._set_prev(connection_edge2._prev)
        diagonal1._set_next(connection_edge2)
        diagonal2._set_next(connection_edge1)

        self._has_diagonals = True

        return diagonal1

    def __len__(self) -> int:
        return self._number_of_vertices

class Vertex:
    def __init__(self, point: Point):
        self._point = point
        self._edge: HalfEdge = HalfEdge(self)

    @property
    def point(self) -> Point:
        return self._point

    @property
    def x(self) -> float:
        return self._point.x

    @property
    def y(self) -> float:
        return self._point.y

    @property
    def edge(self) -> HalfEdge:
        return self._edge

    def __repr__(self) -> str:
        return f"Vertex@{self._point}"

class HalfEdge:
    def __init__(self, origin: Vertex):
        self._origin = origin
        self._twin: HalfEdge = self
        self._prev: HalfEdge = self
        self._next: HalfEdge = self

    @property
    def origin(self) -> Vertex:
        return self._origin

    @property
    def destination(self) -> Vertex:
        return self._twin._origin

    @property
    def upper_and_lower(self) -> tuple[Vertex, Vertex]:
        p, q = self._origin, self.destination
        if p.y > q.y or (p.y == q.y and p.x < q.x):
            return p, q
        else:
            return q, p

    @property
    def twin(self) -> HalfEdge:
        return self._twin

    @property
    def prev(self) -> HalfEdge:
        return self._prev

    @property
    def next(self) -> HalfEdge:
        return self._next

    def _set_twin(self, twin: HalfEdge):
        self._twin = twin
        twin._twin = self

    def _set_prev(self, prev: HalfEdge):
        self._prev = prev
        prev._next = self

    def _set_next(self, next: HalfEdge):
        self._next = next
        next._prev = self

    def __repr__(self) -> str:
        return f"Edge@{self._origin._point}->{self.destination._point}"
