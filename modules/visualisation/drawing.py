from __future__ import annotations
from typing import Any, Iterable, Iterator, Optional
from abc import ABC, abstractmethod
from contextlib import contextmanager
import time

from geometry import Point, PointReference

from ipycanvas import Canvas, hold_canvas


class AnimationEvent(ABC):
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


DEFAULT_POINT_RADIUS = 5

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

    def draw_point(self, point: Point, radius: int = DEFAULT_POINT_RADIUS, transparent: bool = False):
        if transparent:
            self._canvas.fill_style = self.transparent_style
        self._canvas.fill_circle(point.x, point.y, radius)
        if transparent:
            self._canvas.fill_style = self.opaque_style

    def draw_point_outline(self, point: Point, radius: int = DEFAULT_POINT_RADIUS):
        self._canvas.stroke_circle(point.x, point.y, radius)

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

    def _get_drawing_mode_state(self, default: Any = None) -> Any:
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
        self._drawing_mode.animate(self, animation_events, animation_time_step)


class DrawingMode(ABC):
    @abstractmethod
    def draw(self, drawer: Drawer, points: Iterable[Point]):
        pass

    @abstractmethod
    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        pass


class PointsMode(DrawingMode):
    def draw(self, drawer: Drawer, points: Iterable[Point]):
        with drawer.main_canvas.hold():
            for point in points:
                drawer.main_canvas.draw_point(point)

    def _draw_animation_step(self, drawer: Drawer, points: list[Point]):
        with drawer.main_canvas.hold():
            drawer.main_canvas.clear()
            if points:
                for point in points[:-1]:
                    drawer.main_canvas.draw_point(point)
                drawer.main_canvas.draw_point(points[-1], radius = 12, transparent = True)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        drawer.clear()

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
                for point in points[:-1]:
                    drawer.main_canvas.draw_point(point)
                drawer.main_canvas.draw_point(points[-1], radius = 12, transparent = True)
                left_sweep_line_point = Point(0, points[-1].y)
                right_sweep_line_point = Point(drawer.front_canvas.width, points[-1].y)
                drawer.front_canvas.draw_path((left_sweep_line_point, right_sweep_line_point))


class PathMode(DrawingMode):
    def __init__(self, draw_vertices: bool):
        self._draw_vertices = draw_vertices
        self._animation_path = []

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        path = []
        previous_point = drawer._get_drawing_mode_state()
        if previous_point is not None:
            path.append(previous_point)
        path.extend(points)
        if path:
            drawer._set_drawing_mode_state(path[-1])

        with drawer.main_canvas.hold():
            if self._draw_vertices:
                for point in path:
                    drawer.main_canvas.draw_point(point)
            drawer.main_canvas.draw_path(path)

    def _draw_animation_step(self, drawer: Drawer):
        with drawer.main_canvas.hold():
            drawer.main_canvas.clear()
            if self._draw_vertices and self._animation_path:
                for point in self._animation_path[:-1]:
                    drawer.main_canvas.draw_point(point)
                drawer.main_canvas.draw_point(self._animation_path[-1], radius = 12, transparent = True)
            drawer.main_canvas.draw_path(self._animation_path[:-1])
            drawer.main_canvas.draw_path(self._animation_path[-2:], transparent = True)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        drawer.clear()

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
            self._draw_animation_step(drawer)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, self._animation_path)
        self._animation_path.clear()

class PolygonMode(PathMode):
    def __init__(self, draw_vertices: bool, draw_interior: bool):
        super().__init__(draw_vertices)
        self._draw_interior = draw_interior

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        polygon = drawer._get_drawing_mode_state(default = [])
        polygon.extend(points)

        drawer.main_canvas.clear()
        if self._draw_interior:
            drawer.back_canvas.clear()

        with drawer.main_canvas.hold(), drawer.back_canvas.hold():
            if self._draw_vertices:
                for point in polygon:
                    drawer.main_canvas.draw_point(point)
            drawer.main_canvas.draw_polygon(polygon)
            if self._draw_interior:
                drawer.back_canvas.draw_polygon(polygon, stroke = False, fill = True, transparent = True)

    def _polygon_event_iterator(self, animation_events: Iterable[AnimationEvent]) -> Iterator[AnimationEvent]:
        yield from animation_events
        yield AppendEvent(self._animation_path[0])

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        super().animate(drawer, self._polygon_event_iterator(animation_events), animation_time_step)

class ChansHullMode(PolygonMode):
    @classmethod
    def from_polygon_mode(cls, polygon_mode: PolygonMode) -> ChansHullMode:
        return cls(polygon_mode._draw_vertices, polygon_mode._draw_interior)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        drawer.clear()

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
                    if isinstance(event.point, PointReference) and event.point.get_container() is not container:
                        container = event.point.get_container()
                        with drawer.front_canvas.hold():
                            drawer.front_canvas.clear()
                            drawer.front_canvas.draw_polygon(container)
                        time.sleep(animation_time_step)

            event.execute_on(self._animation_path)
            self._draw_animation_step(drawer)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, self._animation_path)
        self._animation_path.clear()


class FixedVertexNumberPathsMode(DrawingMode):
    def __init__(self, vertex_number: int, draw_vertices: bool):
        if vertex_number < 1:
            return ValueError("Vertex number needs to be positive.")
        self._vertex_number = vertex_number
        self._draw_vertices = draw_vertices

    def draw(self, drawer: Drawer, points: Iterable[Point]):      # TODO: Maybe implement this differently.
        path = drawer._get_drawing_mode_state(default = [])

        with drawer.main_canvas.hold():
            for point in points:
                if self._draw_vertices:
                    drawer.main_canvas.draw_point(point, transparent = True)
                path.append(point)
                drawer.main_canvas.draw_path(path[-2:], transparent = True)
                if len(path) == self._vertex_number:
                    for path_point in path:
                        drawer.main_canvas.draw_point(path_point)
                    drawer.main_canvas.draw_path(path)
                    path.clear()

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):   # TODO: Implement this.
        pass

class LineSegmentsMode(FixedVertexNumberPathsMode):
    def __init__(self, draw_vertices: bool):
        super().__init__(2, draw_vertices)

class FixedVertexNumberPolygonsMode(FixedVertexNumberPathsMode):        # TODO: Implement this.
    pass

class TrianglesMode(FixedVertexNumberPolygonsMode):
    def __init__(self, draw_vertices: bool):
        super().__init__(3, draw_vertices)
