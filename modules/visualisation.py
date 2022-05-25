from typing import Callable
from ipycanvas import Canvas, MultiCanvas, hold_canvas
from ipywidgets import Output, Button, Label, Checkbox, HBox, IntSlider
from IPython.display import display
from geometry import Point, Polygon, AppendEvent
import time
from threading import Lock
import numpy as np

class Visualisation:
    def __init__(self):
        self.width = 600
        self.height = 250

        self.lock = Lock()
        self.points = set()

        self.out = Output(layout={'border': '1px solid black', 'width': '600px'})

        @self.out.capture()
        def handle_mouse_down(x, y):
            if self.lock.acquire(blocking=False):       # TODO: Does this lead to problems?
                self.add_points([Point(x, self.height - y)])
                self.clear_background()
                self.lock.release()

        self.mouse_down = handle_mouse_down
        self.canvas = None
        self.init_canvas()

        self.buttons = [
            Button(
                description="Clear",
                disabled=False,
                button_style="",
                tooltip="Click me"
            ),
            Button(
                description="Random instance",
                disabled=False,
                button_style="",
                tooltip="Click me"
            )    
        ]
        clear_callback = lambda _: self.clear()
        self.buttons[0].on_click(lambda _: self._callback_with_lock(clear_callback))
        def random_callback(x):
            self.clear()
            self.add_points([Point(             # TODO: improve this
                np.random.randint(low=20, high=self.width - 20),
                np.random.randint(low=20, high=self.height - 20),
            ) for _ in range(100)])
        self.buttons[1].on_click(lambda _: self._callback_with_lock(random_callback))

        self.number_label = Label("Number of points: 0 (of maximum 1000)")
        self.runtime_label = Label(value="Runtime: ")

        self.checkbox = Checkbox(
            value=False,
            description='Animate',
            disabled=False,
            indent=False
        )

        self.animation_started = False

        self.slider = IntSlider(
            value=5,
            min=1,
            max=10,
            step=1,
            description = "Speed",
            disabled = False,
        )

    def init_canvas(self) -> MultiCanvas:
        canvas = MultiCanvas(3, width=self.width, height=self.height)
        canvas.on_mouse_down(self.mouse_down)

        canvas[0].line_width = 2
        canvas[0].stroke_style = "blue"
        canvas[0].fill_style = "rgba(0, 0, 255, 0.2)"
        canvas[0].translate(0, self.height)
        canvas[0].scale(1, -1)

        canvas[1].fill_style = "orange"
        canvas[1].translate(0, self.height)
        canvas[1].scale(1, -1)

        canvas[2].stroke_style = "black"            # TODO: more layers? own mode for each layer?
        canvas[2].translate(0, self.height)
        canvas[2].scale(1, -1)

        with hold_canvas(canvas[1]):
            for point in self.points:
                canvas[1].fill_circle(point.x, point.y, 5)

        self.out.clear_output(wait=True)
        with self.out:
            display(canvas)
        self.canvas = canvas

    def draw_path(self, cv: int, points: list[Point], close=False, fill=False):
        if points:
            self.canvas[cv].begin_path()
            self.canvas[cv].move_to(points[0].x, points[0].y)
            for point in points[1:]:
                self.canvas[cv].line_to(point.x, point.y)
            if close:
                self.canvas[cv].close_path()
            self.canvas[cv].stroke()
            if fill:
                self.canvas[cv].fill()

    def draw_polygon(self, polygon: Polygon, animate=False):
        with hold_canvas(self.canvas[0]), hold_canvas(self.canvas[2]):
            if animate:
                if polygon.points:
                    polygon.append(polygon.points[0])
                current_points = []
                background_points = []
                self.animation_started = True
                step_time = 1100 - 100 * self.slider.value
                for event in polygon.events:
                    if isinstance(event, AppendEvent) and current_points and event.point == current_points[-1]:
                        continue

                    background_points.clear()
                    event.execute_on(current_points, background_points)

                    if background_points:
                        self.canvas[2].clear()
                        self.draw_path(2, background_points, close=True)
                        self.canvas[2].sleep(2 * step_time)
                        self.canvas[0].sleep(step_time)
                    else:
                        self.canvas[2].sleep(step_time)

                    self.canvas[0].clear()
                    self.draw_path(0, current_points)
                    self.canvas[0].fill_circle(current_points[-1].x, current_points[-1].y, 10)
                    self.canvas[0].sleep(step_time)
                self.canvas[0].clear()
                self.canvas[2].clear()
            self.draw_path(0, polygon.points, close=True, fill=True)

    def add_points(self, points: list[Point]):
        if len(self.points) + len(points) > 1000:   # TODO: not accurate
            return
        with hold_canvas(self.canvas[1]):
            for point in points:
                self.points.add(point)
                self.canvas[1].fill_circle(point.x, point.y, 5)
        self.number_label.value = f"Number of points: {len(self.points)} (of maximum 1000)"

    def register_button(self, description: str, callback: Callable):
        button = Button(
            description=description,
            disabled=False,
            button_style="",
            tooltip="Some button"
        )
        button.on_click(lambda _: self._callback_with_lock(callback))
        self.buttons.append(button)

    def _callback_with_lock(self, callback: Callable):      # TODO: This might not be optimal.
        if self.lock.acquire(blocking=False):
            for button in self.buttons:
                button.disabled = True
            callback("")
            for button in self.buttons:
                button.disabled = False
            self.lock.release()

    def register_instance(self, name: str, points: list[Point]):
        self.register_button(name, lambda _: self._instance_callback(points))

    def _instance_callback(self, points: list[Point]):
        self.clear()
        self.add_points(points)     # TODO: mode="points"
        
    def register_algorithm(self, name: str, algo: Callable):
        self.register_button(name, lambda _: self._algorithm_callback(algo))

    def _algorithm_callback(self, algo):
        self.clear_background()
        start = time.time()
        result = algo(self.points)
        end = time.time()
        self.draw_polygon(result, animate=self.checkbox.value)     # TODO: mode="polygon"
        self.runtime_label.value = f"Runtime: {1000 * (end - start)} ms"
    
    def clear(self):
        self.clear_points()
        self.clear_background()

    def clear_background(self):
        self.canvas[0].clear()
        if self.animation_started:
            self.animation_started = False
            self.init_canvas()

    def clear_points(self):
        self.points.clear()
        self.canvas[1].clear()
        self.number_label.value = f"Number of points: {len(self.points)} (of maximum 1000)"

    def display(self):
        display(self.out)
        display(HBox(self.buttons[:3]))     # TODO: Separate instances from algorithms.
        display(HBox(self.buttons[3:]))
        display(HBox([self.checkbox, self.slider]))
        display(self.number_label)
        display(self.runtime_label)