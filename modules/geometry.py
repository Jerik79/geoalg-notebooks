from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Iterable, Iterator, Optional, Union, Any
from enum import Enum, auto
from collections import OrderedDict
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


class LineSegment(GeometricPrimitive):
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


class Intersections(GeometricPrimitive):
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


class DoublyConnectedPolygon(GeometricPrimitive):
    def __init__(self):
        self.clear()

    def clear(self):
        self._is_closed: bool = False
        self._root_vertex: Optional[Vertex] = None
        self._previous_vertex: Optional[Vertex] = None
        self._number_of_vertices: int = 0

    def _vertices(self) -> Iterator[Vertex]:    # TODO: This loops infinitely if not closed...
        if self._root_vertex is None:
            return ()

        yield self._root_vertex
        current_edge = self._root_vertex._edge
        while current_edge is not None and current_edge.destination is not self._root_vertex:
            yield current_edge.destination
            current_edge = current_edge.destination._edge

    def points(self) -> Iterator[Point]:
        for vertex in self._vertices():
            if vertex._edge is not None:
                incident_edge = vertex._edge._prev._twin
                while incident_edge is not vertex._edge and incident_edge._prev._twin is not vertex._edge:
                    yield vertex._point
                    yield incident_edge.destination._point
                    incident_edge = incident_edge._prev._twin

    def animation_events(self) -> Iterator[AnimationEvent]:
        pass

    def add_vertex(self, vertex_position: Point) -> Optional[Vertex]:   # TODO: return edge?
        if self._is_closed:
            return None

        vertex = Vertex(vertex_position)

        if self._previous_vertex is None:
            self._root_vertex = vertex
        else:
            forward_edge = HalfEdge(self._previous_vertex)
            backward_edge = HalfEdge(vertex)
            vertex._edge = backward_edge
            forward_edge._make_twin(backward_edge)
            forward_edge._make_next(backward_edge)
            if self._previous_vertex._edge is None:
                forward_edge._make_prev(backward_edge)
            else:
                forward_edge._make_prev(self._previous_vertex._edge._twin)
                backward_edge._make_next(self._previous_vertex._edge)
            self._previous_vertex._edge = forward_edge

        self._previous_vertex = vertex
        self._number_of_vertices += 1

        return vertex

    """ def is_triangle(self) -> bool:
        return self._is_closed and len(list(zip(self._vertices(), range(4)))) == 3 """

    def check_simplicity(vertex_position: Optional[Point]) -> bool:     # TODO: how to go about this?
        pass

    def close(self):        # TODO: Use close for type transformation.
        if self._is_closed or self._number_of_vertices < 3:    # TODO: which checks are necessary?
            return

        forward_edge = HalfEdge(self._previous_vertex)
        backward_edge = HalfEdge(self._root_vertex)
        forward_edge._make_twin(backward_edge)
        forward_edge._make_next(self._root_vertex._edge)
        backward_edge._make_prev(self._root_vertex._edge._twin)
        forward_edge._make_prev(self._previous_vertex._edge._twin)
        backward_edge._make_next(self._previous_vertex._edge)
        self._previous_vertex._edge = forward_edge

        # find topmost vertex (always a start vertex)
        topmost_vertex = self._root_vertex
        for vertex in self._vertices():
            if vertex.y > topmost_vertex.y or (vertex.y == topmost_vertex.y and vertex.x < topmost_vertex.x):
                topmost_vertex = vertex

        # turn edges around if they are not in counterclockwise direction around polygonal face
        ort = topmost_vertex.orientation(topmost_vertex._edge._prev._origin, topmost_vertex._edge.destination)
        if ort is not Orientation.RIGHT:
            self._root_vertex._edge = self._root_vertex._edge._prev._twin
            current_vertex = self._root_vertex._edge.destination
            while current_vertex is not self._root_vertex:
                current_vertex._edge = current_vertex._edge._prev._twin
                current_vertex = current_vertex._edge.destination

        self._is_closed = True

    # edge1 and edge2 need to bound the same face, so one could store the incident face for each edge.
    # However, adding a diagonal would then require updating these faces in O(n) time...
    def add_diagonal(self, edge1: HalfEdge, edge2: HalfEdge) -> Optional[HalfEdge]:
        vertex1 = edge1._origin
        vertex2 = edge2._origin

        if not self._is_closed and vertex1 is not vertex2 and vertex1._edge.destination is not vertex2 \
             and vertex2._edge.destination is not vertex1:     # TODO: which checks are necessary?
            return None
        
        diagonal1 = HalfEdge(vertex1)
        diagonal2 = HalfEdge(vertex2)
        diagonal1._make_twin(diagonal2)
        diagonal1._make_prev(edge1._prev)
        diagonal2._make_prev(edge2._prev)
        diagonal1._make_next(edge2)
        diagonal2._make_next(edge1)

        return diagonal1

    def __len__(self) -> int:
        return self._number_of_vertices

class Vertex:
    def __init__(self, point: Point):
        self._point = point
        self._edge: Optional[HalfEdge] = None

    @property
    def x(self) -> float:
        return self._point.x

    @property
    def y(self) -> float:
        return self._point.y

    def orientation(self, source: Vertex, target: Vertex) -> Orientation:
        self._point.orientation(source._point, target._point)

class HalfEdge:
    def __init__(self, origin: Vertex):
        self._origin = origin
        self._twin: Optional[HalfEdge] = None
        self._next: Optional[HalfEdge] = None
        self._prev: Optional[HalfEdge] = None

    @property
    def destination(self) -> Vertex:
        return self._twin._origin

    def _make_twin(self, twin: HalfEdge):
        self._twin = twin
        twin._twin = self

    def _make_prev(self, prev: HalfEdge):
        self._prev = prev
        prev._next = self

    def _make_next(self, next: HalfEdge):
        self._next = next
        next._prev = self
