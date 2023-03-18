from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import contextmanager
from itertools import islice
import time
from typing import Any, Iterable, Iterator, Optional

from ..geometry.core import AnimationEvent, AppendEvent, ClearEvent, Point, PointReference, PopEvent, SetEvent

from ipycanvas import Canvas, hold_canvas


class CanvasDrawingHandle:
    def __init__(self, canvas: Canvas):
        self._canvas = canvas
        self.set_colour(0, 0, 0)

    @contextmanager
    def hold(self):
        with hold_canvas(self._canvas):
            yield

    def set_colour(self, r: int, g: int, b: int):
        self.opaque_style = f"rgb({r}, {g}, {b})"
        self.transparent_style = f"rgba({r}, {g}, {b}, 0.25)"

        self._canvas.stroke_style = self.opaque_style
        self._canvas.fill_style = self.opaque_style

    def clear(self):
        self._canvas.clear()

    def draw_point(self, point: Point, radius: int, transparent: bool = False):
        if radius <= 0:
            return
        if transparent:
            self._canvas.fill_style = self.transparent_style
        self._canvas.fill_circle(point.x, point.y, radius)
        if transparent:
            self._canvas.fill_style = self.opaque_style

    def draw_points(self, points: Iterable[Point], radius: int, transparent: bool = False):
        if radius <= 0:
            return
        if transparent:
            self._canvas.fill_style = self.transparent_style
        for point in points:
            self._canvas.fill_circle(point.x, point.y, radius)
        if transparent:
            self._canvas.fill_style = self.opaque_style

    def draw_path(self, points: Iterable[Point], close: bool = False, stroke: bool = True,
    fill: bool = False, transparent: bool = False):
        points_iterator = iter(points)
        first_point = next(points_iterator, None)
        if first_point is None:
            return

        self._canvas.begin_path()
        self._canvas.move_to(first_point.x, first_point.y)
        for point in points_iterator:
            self._canvas.line_to(point.x, point.y)
        
        if close:
            self._canvas.close_path()
        if transparent:
            self._canvas.stroke_style = self.transparent_style
            self._canvas.fill_style = self.transparent_style
        if stroke:
            self._canvas.stroke()
        if fill:
            self._canvas.fill(rule_or_path = "nonzero")
        if transparent:
            self._canvas.stroke_style = self.opaque_style
            self._canvas.fill_style  = self.opaque_style

    def draw_polygon(self, points: Iterable[Point], stroke: bool = True,
    fill: bool = False, transparent: bool = False):
        self.draw_path(points, close = True, stroke = stroke, fill = fill, transparent = transparent)

    @property
    def width(self) -> float:
        return self._canvas.width


class Drawer:
    def __init__(self, drawing_mode: DrawingMode, back_canvas: CanvasDrawingHandle,
    main_canvas: CanvasDrawingHandle, front_canvas: CanvasDrawingHandle):
        self._drawing_mode = drawing_mode
        self._drawing_mode_state = None
        self.back_canvas = back_canvas
        self.main_canvas = main_canvas
        self.front_canvas = front_canvas

    def _get_drawing_mode_state(self, default: Any = None) -> Any:    # TODO: This could be generic.
        if self._drawing_mode_state is None:
            self._drawing_mode_state = default
        return self._drawing_mode_state

    def _set_drawing_mode_state(self, state: Any):
        self._drawing_mode_state = state

    def clear(self):
        self._drawing_mode_state = None
        self.back_canvas.clear()
        self.main_canvas.clear()
        self.front_canvas.clear()

    def draw(self, points: Iterable[Point]):
        self._drawing_mode.draw(self, points)

    def animate(self, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        self.clear()
        self._drawing_mode.animate(self, animation_events, animation_time_step)


DEFAULT_POINT_RADIUS = 5
DEFAULT_HIGHLIGHT_RADIUS = 12

class DrawingMode(ABC):    # TODO: Maybe we can DRY this file after all...
    @abstractmethod
    def draw(self, drawer: Drawer, points: Iterable[Point]):
        pass

    @abstractmethod
    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        pass


class PointsMode(DrawingMode):
    def __init__(self, point_radius: int = DEFAULT_POINT_RADIUS, highlight_radius: int = DEFAULT_HIGHLIGHT_RADIUS):
        self._point_radius = point_radius
        self._highlight_radius = highlight_radius

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        with drawer.main_canvas.hold():
            drawer.main_canvas.draw_points(points, self._point_radius)

    def _draw_animation_step(self, drawer: Drawer, points: list[Point]):
        with drawer.main_canvas.hold():
            drawer.main_canvas.clear()
            if points:
                drawer.main_canvas.draw_points(points[:-1], self._point_radius)
                drawer.main_canvas.draw_point(points[-1], self._highlight_radius, transparent = True)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        points: list[Point] = []

        event_iterator = iter(animation_events)
        next_event = next(event_iterator, None)

        while next_event is not None:
            event = next_event
            next_event = next(event_iterator, None)

            if points:
                if isinstance(event, PopEvent) and isinstance(next_event, AppendEvent):    # TODO: Maybe this can be done more elegantly.
                    event = SetEvent(-1, next_event.point)
                if isinstance(event, AppendEvent) or (isinstance(event, SetEvent) and event.key == -1):
                    if event.point == points[-1]:
                        continue

            event.execute_on(points)
            if isinstance(event, PopEvent) and next_event is None:
                break
            self._draw_animation_step(drawer, points)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, points)

class SweepLineMode(PointsMode):
    def _draw_animation_step(self, drawer: Drawer, points: list[Point]):
        with drawer.main_canvas.hold(), drawer.front_canvas.hold():
            drawer.main_canvas.clear()
            drawer.front_canvas.clear()
            if points:
                drawer.main_canvas.draw_points(points[:-1], self._point_radius)
                drawer.main_canvas.draw_point(points[-1], self._highlight_radius, transparent = True)
                left_sweep_line_point = Point(0, points[-1].y)
                right_sweep_line_point = Point(drawer.front_canvas.width, points[-1].y)
                drawer.front_canvas.draw_path((left_sweep_line_point, right_sweep_line_point))

class ArtGalleryMode(PointsMode):
    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        diagonal_points: list[Point] = []

        event_iterator = iter(animation_events)
        event = next(event_iterator, None)

        while event is not None and not isinstance(event, ClearEvent):
            event.execute_on(diagonal_points)
            event = next(event_iterator, None)

        with drawer.back_canvas.hold():
            for i in range(0, len(diagonal_points), 2):
                drawer.back_canvas.draw_path(diagonal_points[i:i + 2], transparent = True)

        super().animate(drawer, event_iterator, animation_time_step)


class PathMode(DrawingMode):
    def __init__(self, vertex_radius: int = DEFAULT_POINT_RADIUS, highlight_radius: int = DEFAULT_HIGHLIGHT_RADIUS):
        self._vertex_radius = vertex_radius
        self._highlight_radius = highlight_radius
        self._animation_path = []

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        path = []
        previous_vertex: Optional[Point] = drawer._get_drawing_mode_state()
        if previous_vertex is not None:
            path.append(previous_vertex)
        path.extend(points)
        if path:
            drawer._set_drawing_mode_state(path[-1])

        with drawer.main_canvas.hold():
            drawer.main_canvas.draw_points(path, self._vertex_radius)
            drawer.main_canvas.draw_path(path)

    def _draw_animation_step(self, drawer: Drawer):
        with drawer.main_canvas.hold():
            drawer.main_canvas.clear()
            if self._animation_path:
                drawer.main_canvas.draw_points(self._animation_path[:-1], self._vertex_radius)
                drawer.main_canvas.draw_point(self._animation_path[-1], self._highlight_radius, transparent = True)
                drawer.main_canvas.draw_path(self._animation_path[:-1])
                drawer.main_canvas.draw_path(self._animation_path[-2:], transparent = True)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        event_iterator = iter(animation_events)
        next_event = next(event_iterator, None)

        while next_event is not None:
            event = next_event
            next_event = next(event_iterator, None)

            if self._animation_path:
                if isinstance(event, PopEvent) and isinstance(next_event, AppendEvent):
                    event = SetEvent(-1, next_event.point)
                if isinstance(event, AppendEvent) or (isinstance(event, SetEvent) and event.key == -1):
                    if event.point == self._animation_path[-1]:
                        continue

            event.execute_on(self._animation_path)
            if isinstance(event, PopEvent) and next_event is None:
                break
            self._draw_animation_step(drawer)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, self._animation_path)
        self._animation_path.clear()

class PolygonMode(PathMode):           # TODO: If possible, maybe use composition instead of inheritance.
    def __init__(self, mark_closing_edge: bool, draw_interior: bool, vertex_radius: int = DEFAULT_POINT_RADIUS,
    highlight_radius: int = DEFAULT_HIGHLIGHT_RADIUS):
        super().__init__(vertex_radius = vertex_radius, highlight_radius = highlight_radius)
        self._mark_closing_edge = mark_closing_edge
        self._draw_interior = draw_interior

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        polygon: list[Point] = drawer._get_drawing_mode_state(default = [])
        polygon.extend(points)

        drawer.main_canvas.clear()    # TODO: A clear is needed because the polygon can change. This is inconsistent with other modes.
        if self._draw_interior:
            drawer.back_canvas.clear()

        with drawer.main_canvas.hold(), drawer.back_canvas.hold():
            drawer.main_canvas.draw_points(polygon, self._vertex_radius)
            if self._mark_closing_edge and polygon:
                drawer.main_canvas.draw_path(polygon)
                drawer.main_canvas.draw_path((polygon[0], polygon[-1]), transparent = True)
            else:
                drawer.main_canvas.draw_polygon(polygon)
            if self._draw_interior:
                drawer.back_canvas.draw_polygon(polygon, stroke = False, fill = True, transparent = True)

    def _polygon_event_iterator(self, animation_events: Iterable[AnimationEvent]) -> Iterator[AnimationEvent]:
        yield from animation_events
        yield AppendEvent(self._animation_path[0])
        yield PopEvent()

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        super().animate(drawer, self._polygon_event_iterator(animation_events), animation_time_step)

class ChansHullMode(PolygonMode):
    @classmethod
    def from_polygon_mode(cls, polygon_mode: PolygonMode) -> ChansHullMode:
        return ChansHullMode(
            polygon_mode._mark_closing_edge,
            polygon_mode._draw_interior,
            vertex_radius = polygon_mode._vertex_radius,
            highlight_radius = polygon_mode._highlight_radius
        )

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        container: Optional[list[Point]] = None

        event_iterator = self._polygon_event_iterator(animation_events)
        next_event = next(event_iterator, None)

        while next_event is not None:
            event = next_event
            next_event = next(event_iterator, None)

            if self._animation_path:
                if isinstance(event, PopEvent) and isinstance(next_event, AppendEvent):
                    event = SetEvent(-1, next_event.point)
                if isinstance(event, AppendEvent) or (isinstance(event, SetEvent) and event.key == -1):
                    if event.point == self._animation_path[-1]:
                        continue
                    if isinstance(event.point, PointReference) and event.point.container is not container:
                        container = event.point.container
                        with drawer.front_canvas.hold():
                            drawer.front_canvas.clear()
                            drawer.front_canvas.draw_polygon(container)
                        time.sleep(animation_time_step)

            event.execute_on(self._animation_path)
            if isinstance(event, PopEvent) and next_event is None:
                break
            self._draw_animation_step(drawer)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, self._animation_path)
        self._animation_path.clear()


class FixedVertexNumberPathsMode(DrawingMode):
    def __init__(self, vertex_number: int, vertex_radius: int = DEFAULT_POINT_RADIUS,
    highlight_radius: int = DEFAULT_HIGHLIGHT_RADIUS):
        if vertex_number < 1:
            return ValueError("Vertex number needs to be positive.")
        self._vertex_number = vertex_number
        self._vertex_radius = vertex_radius
        self._highlight_radius = highlight_radius

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        vertex_queue: list[Point] = drawer._get_drawing_mode_state(default = [])
        initial_queue_length = len(vertex_queue)
        vertex_queue.extend(points)

        with drawer.main_canvas.hold():
            i, j = 0, self._vertex_number
            while j <= len(vertex_queue):
                path = vertex_queue[i:j]
                drawer.main_canvas.draw_points(path, self._vertex_radius)
                drawer.main_canvas.draw_path(path)
                i, j = j, j + self._vertex_number

            if i == 0:
                offset = int(initial_queue_length != 0)
                subpath = vertex_queue[initial_queue_length - offset:]
            else:
                offset = 0
                subpath = vertex_queue[i:]
                drawer._set_drawing_mode_state(subpath)
            drawer.main_canvas.draw_points(islice(subpath, offset, None), self._vertex_radius, transparent = True)
            drawer.main_canvas.draw_path(subpath, transparent = True)

    def _draw_animation_step(self, drawer: Drawer, points: list[Point]):
        with drawer.main_canvas.hold():
            drawer.main_canvas.clear()

            i, j = 0, self._vertex_number
            while j < len(points):
                path = points[i:j]
                drawer.main_canvas.draw_points(path, self._vertex_radius)
                drawer.main_canvas.draw_path(path)
                i, j = j, j + self._vertex_number

            path = points[i:]
            drawer.main_canvas.draw_points(path, self._highlight_radius, transparent = True)
            drawer.main_canvas.draw_path(path, transparent = True)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        points: list[Point] = []

        event_iterator = iter(animation_events)
        next_event = next(event_iterator, None)

        while next_event is not None:
            event = next_event
            next_event = next(event_iterator, None)

            if points:
                if isinstance(event, PopEvent) and isinstance(next_event, AppendEvent):
                    event = SetEvent(-1, next_event.point)
                if isinstance(event, AppendEvent) or (isinstance(event, SetEvent) and event.key == -1):
                    if event.point == points[-1] and len(points) % self._vertex_number != 0:
                        continue

            event.execute_on(points)
            if isinstance(event, AppendEvent) or (isinstance(event, SetEvent) and event.key == -1):
                if isinstance(next_event, AppendEvent) or (isinstance(next_event, SetEvent) and next_event.key == -1):
                    if len(points) % self._vertex_number != 0:
                        continue
            if isinstance(event, PopEvent) and next_event is None:
                break
            self._draw_animation_step(drawer, points)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, points)

class LineSegmentsMode(FixedVertexNumberPathsMode):
    def __init__(self, vertex_radius: int = DEFAULT_POINT_RADIUS,
    highlight_radius: int = DEFAULT_HIGHLIGHT_RADIUS):
        super().__init__(2, vertex_radius, highlight_radius)


class MonotonePartitioningMode(DrawingMode):    # TODO: If possible, this could maybe make use of composition too.
    def __init__(self, animate_sweep_line: bool, vertex_radius: int = DEFAULT_POINT_RADIUS,
    highlight_radius: int = DEFAULT_HIGHLIGHT_RADIUS):
        self._animate_sweep_line = animate_sweep_line
        self._vertex_radius = vertex_radius
        self._highlight_radius = highlight_radius

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        points: list[Point] = list(points)
        with drawer.main_canvas.hold():
            drawer.main_canvas.draw_points(points, self._vertex_radius)
            for i in range(0, len(points), 2):
                drawer.main_canvas.draw_path(points[i:i + 2])

    def _draw_animation_step(self, drawer: Drawer, points: list[Point]):
        with drawer.main_canvas.hold(), drawer.front_canvas.hold():
            drawer.main_canvas.clear()
            drawer.front_canvas.clear()

            if not points:
                return
            elif len(points) % 2 == 0:
                diagonal_points = points
                event_point = points[-2]
            else:
                diagonal_points = points[:-1]
                event_point = points[-1]

            drawer.main_canvas.draw_points(diagonal_points, self._vertex_radius)
            drawer.main_canvas.draw_point(event_point, self._highlight_radius, transparent = True)
            for i in range(0, len(diagonal_points), 2):
                drawer.main_canvas.draw_path(diagonal_points[i:i + 2])
            if self._animate_sweep_line:
                left_sweep_line_point = Point(0, event_point.y)
                right_sweep_line_point = Point(drawer.front_canvas.width, event_point.y)
                drawer.front_canvas.draw_path((left_sweep_line_point, right_sweep_line_point))

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        points: list[Point] = []

        event_iterator = iter(animation_events)
        next_event = next(event_iterator, None)

        while next_event is not None:
            event = next_event
            next_event = next(event_iterator, None)

            if points:
                if isinstance(event, PopEvent) and isinstance(next_event, AppendEvent):
                    event = SetEvent(-1, next_event.point)
                if isinstance(event, AppendEvent) or (isinstance(event, SetEvent) and event.key == -1):
                    if event.point == points[-1] and len(points) % 2 != 0:
                        continue

            event.execute_on(points)
            if len(points) >= 3 and len(points) % 2 == 1 and points[-1] == points[-3]:
                continue
            if isinstance(event, PopEvent) and next_event is None:
                break
            self._draw_animation_step(drawer, points)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, points)
