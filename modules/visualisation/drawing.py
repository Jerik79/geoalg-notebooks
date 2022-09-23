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
        self.transparent_style = f"rgba({r}, {g}, {b}, 0.2)"

        self._canvas.stroke_style = self.opaque_style
        self._canvas.fill_style = self.opaque_style

    def set_line_width(self, line_width: float):
        self._canvas.line_width = line_width

    def clear(self):
        self._canvas.clear()

    def draw_point(self, point: Point, radius: int = DEFAULT_POINT_RADIUS, transparent: bool = False):
        if transparent:
            self._canvas.fill_style = self.transparent_style
        self._canvas.fill_circle(float(point.x), float(point.y), radius)
        if transparent:
            self._canvas.fill_style = self.opaque_style

    def draw_point_outline(self, point: Point, radius: int = DEFAULT_POINT_RADIUS):
        self._canvas.stroke_circle(float(point.x), float(point.y), radius)

    def draw_path(self, points: Iterable[Point], close = False, stroke = True, fill = False):
        points_iterator = iter(points)
        first_point = next(points_iterator, None)
        if first_point is None:
            return

        self._canvas.begin_path()
        self._canvas.move_to(float(first_point.x), float(first_point.y))
        for point in points_iterator:
            self._canvas.line_to(float(point.x), float(point.y))
        
        if close:
            self._canvas.close_path()
        if stroke:
            self._canvas.stroke()
        if fill:
            self._canvas.fill_style  = self.transparent_style        # TODO: Maybe make this configurable.
            self._canvas.fill()
            self._canvas.fill_style  = self.opaque_style

    def draw_polygon(self, points: Iterable[Point], stroke = True, fill = False):
        self.draw_path(points, True, stroke, fill)


class DrawingMode(ABC):
    @abstractmethod
    def draw(self, drawer: Drawer, points: Iterable[Point]):
        pass

    @abstractmethod
    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        pass

class PointsMode(DrawingMode):
    def draw(self, drawer: Drawer, points: Iterable[Point]):
        with drawer._main_canvas.hold():
            for point in points:
                drawer._main_canvas.draw_point(point)

    def _draw_animation_step(self, drawer: Drawer, points: list[Point]):
        with drawer._main_canvas.hold(), drawer._back_canvas.hold():
            drawer._main_canvas.clear()
            drawer._back_canvas.clear()
            if points:
                for point in points[:-1]:
                    drawer._main_canvas.draw_point(point)
                drawer._main_canvas.draw_point(points[-1], radius = 12, transparent = True)

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
            self._draw_animation_step(drawer, points)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, points)

class PathMode(DrawingMode):
    def __init__(self, draw_vertices: bool):
        self._draw_vertices = draw_vertices
        self._animation_path = []

    def draw(self, drawer: Drawer, points: Iterable[Point]):        # TODO: Maybe utilise state for drawing (incomplete) instances.
        points = list(points)   # TODO: This could be done more efficiently by adjusting CanvasDrawingHandle.

        with drawer._front_canvas.hold(), drawer._main_canvas.hold():
            if self._draw_vertices:
                for point in points:
                    drawer._front_canvas.draw_point(point)
                    drawer._main_canvas.draw_point_outline(point, radius = 6)    # TODO: Maybe make this configurable.
            drawer._main_canvas.draw_path(points)

    def _draw_animation_step(self, drawer: Drawer):
        with drawer._front_canvas.hold(), drawer._main_canvas.hold():
            drawer._front_canvas.clear()
            drawer._main_canvas.clear()
            if self._draw_vertices and self._animation_path:
                for point in self._animation_path[:-1]:
                    drawer._front_canvas.draw_point(point)
                    drawer._main_canvas.draw_point_outline(point, radius = 6)    # TODO: Maybe make this configurable.
                drawer._front_canvas.draw_point(self._animation_path[-1])
                drawer._main_canvas.draw_point(self._animation_path[-1], radius = 12, transparent = True)
            drawer._main_canvas.draw_path(self._animation_path)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        drawer.clear()

        container: Optional[list[Point]] = None

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
                    if isinstance(event.point, PointReference) and event.point.get_container() is not container:
                        container = event.point.get_container()
                        with drawer._highlight_canvas.hold():
                            drawer._highlight_canvas.clear()
                            drawer._highlight_canvas.draw_polygon(container)     # TODO: Maybe make this configurable.
                        time.sleep(animation_time_step)

            event.execute_on(self._animation_path)
            self._draw_animation_step(drawer)
            time.sleep(animation_time_step)

        drawer.clear()
        self.draw(drawer, self._animation_path)
        self._animation_path.clear()

class PolygonMode(PathMode):
    def draw(self, drawer: Drawer, points: Iterable[Point]):
        points = list(points)   # TODO: This could be done more efficiently by adjusting CanvasDrawingHandle.

        with drawer._front_canvas.hold(), drawer._main_canvas.hold(), drawer._back_canvas.hold():
            if self._draw_vertices:
                for point in points:
                    drawer._front_canvas.draw_point(point)
                    drawer._main_canvas.draw_point_outline(point, radius = 6)    # TODO: Maybe make this configurable.
            drawer._main_canvas.draw_polygon(points)
            drawer._back_canvas.draw_polygon(points, stroke = False, fill = True)

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        def polygon_event_iterator() -> Iterator[AnimationEvent]:
            yield from animation_events
            yield AppendEvent(self._animation_path[0])
        super().animate(drawer, polygon_event_iterator(), animation_time_step)

class FixedVertexNumberPathsMode(DrawingMode):
    def __init__(self, length: int, draw_vertices: bool):    # TODO: Check that length is positive.
        self._length = length
        self._draw_vertices = draw_vertices

    def draw(self, drawer: Drawer, points: Iterable[Point]):
        drawing_path = drawer._get_drawing_mode_state([])
        with drawer._front_canvas.hold(), drawer._main_canvas.hold():
            for point in points:
                if self._draw_vertices:
                    drawer._main_canvas.draw_point(point)
                    #drawer.front_canvas.draw_point(point)
                    #drawer.main_canvas.draw_point_outline(point, radius = 6)   # TODO: Maybe make this configurable.
                drawing_path.append(point)
                if len(drawing_path) == self._length:
                    drawer._main_canvas.draw_path(drawing_path)
                    drawing_path.clear()

    def animate(self, drawer: Drawer, animation_events: Iterable[AnimationEvent], animation_time_step: float):   # TODO: Implement this.
        pass

class FixedVertexNumberPolygonsMode(FixedVertexNumberPathsMode):        # TODO: Implement this.
    pass

class LineSegmentsMode(FixedVertexNumberPathsMode):
    def __init__(self, draw_vertices: bool):
        super().__init__(2, draw_vertices)

class TrianglesMode(FixedVertexNumberPolygonsMode):
    def __init__(self, draw_vertices: bool):
        super().__init__(3, draw_vertices)


class Drawer:
    def __init__(self, drawing_mode: DrawingMode, back_canvas: Canvas, main_canvas: Canvas, front_canvas: Canvas,
    highlight_canvas: Canvas):
        self._drawing_mode = drawing_mode
        self._drawing_mode_state = None
        self._back_canvas = CanvasDrawingHandle(back_canvas)
        self._main_canvas = CanvasDrawingHandle(main_canvas)
        self._front_canvas = CanvasDrawingHandle(front_canvas)
        self._highlight_canvas = CanvasDrawingHandle(highlight_canvas)

    def _get_drawing_mode_state(self, default: Any) -> Any:
        if self._drawing_mode_state is None:
            self._drawing_mode_state = default
        return self._drawing_mode_state

    def clear(self):
        self._drawing_mode_state = None
        self._back_canvas.clear()
        self._main_canvas.clear()
        self._front_canvas.clear()
        self._highlight_canvas.clear()

    def draw(self, points: Iterable[Point]):
        self._drawing_mode.draw(self, points)

    def animate(self, animation_events: Iterable[AnimationEvent], animation_time_step: float):
        self._drawing_mode.animate(self, animation_events, animation_time_step)

class InstanceDrawer(Drawer):
    def __init__(self, drawing_mode: DrawingMode, back_canvas: Canvas, main_canvas: Canvas, front_canvas: Canvas,
    highlight_canvas: Canvas):
        super().__init__(drawing_mode, back_canvas, main_canvas, front_canvas, highlight_canvas)

        for canvas in (self._back_canvas, self._main_canvas, self._front_canvas, self._highlight_canvas):       # TODO: Refine this.
            canvas.set_colour(255, 165, 0)
            canvas.set_line_width(2)

class AlgorithmDrawer(Drawer):
    def __init__(self, drawing_mode: DrawingMode, back_canvas: Canvas, main_canvas: Canvas, front_canvas: Canvas,
    highlight_canvas: Canvas):
        super().__init__(drawing_mode, back_canvas, main_canvas, front_canvas, highlight_canvas)

        for canvas in (self._back_canvas, self._main_canvas):
            canvas.set_colour(0, 0, 255)
            canvas.set_line_width(2)

        self._front_canvas.set_colour(255, 165, 0)
        self._highlight_canvas.set_colour(0, 0, 0)
