from typing import Callable
from ipycanvas import Canvas, MultiCanvas, hold_canvas
from ipywidgets import Output, Button, Label, HBox
from IPython.display import display
from geometry import Point
import time
from threading import Lock

class Visualisation:
    def __init__(self):
        self.canvas = MultiCanvas(3, width=420, height=250)

        self.canvas[2].line_width = 5
        self.canvas[2].begin_path()
        self.canvas[2].move_to(0, 0)
        self.canvas[2].line_to(0, self.canvas.height)
        self.canvas[2].line_to(self.canvas.width, self.canvas.height)
        self.canvas[2].line_to(self.canvas.width, 0)
        self.canvas[2].close_path()
        self.canvas[2].stroke()

        self.canvas[0].line_width = 2
        self.canvas[0].translate(0, self.canvas.height)
        self.canvas[0].scale(1, -1)

        self.canvas[1].fill_style = "orange"
        self.canvas[1].translate(0, self.canvas.height)
        self.canvas[1].scale(1, -1)

        self.out = Output()
        @self.out.capture()
        def handle_mouse_down(x, y):
            if self.lock.acquire(blocking=False):
                self.add_points([Point(x, self.canvas.height - y)])
                self.clear_background()
                self.lock.release()
        self.canvas.on_mouse_down(handle_mouse_down)

        self.buttons = [Button(
            description="Clear",
            disabled=False,
            button_style="",
            tooltip="Click me"
        )]
        clear_callback = lambda _: self.clear()
        self.buttons[0].on_click(lambda _: self._callback_with_lock(clear_callback))
        self.lock = Lock()

        self.points = []            # points as set; maximum size; register button that creates random points

        self.label = Label(value="Runtime: ")

    def add_polygon(self, polygon: list[Point]):
        polygon_points = [[(p.x, p.y) for p in polygon]]
        color = [[0, 0, 255]]
        with hold_canvas(self.canvas[0]):
            self.canvas[0].fill_styled_polygons(polygon_points, color, alpha=0.2)
            self.canvas[0].stroke_styled_polygons(polygon_points, color)

    def add_points(self, points: list[Point]):
        self.points.extend(points)
        with hold_canvas(self.canvas[1]):
            for p in points:
                self.canvas[1].fill_circle(p.x, p.y, 5)

    def register_button(self, description: str, callback):
        button = Button(
            description=description,
            disabled=False,
            button_style="",
            tooltip="Some button"
        )
        button.on_click(lambda _: self._callback_with_lock(callback))
        self.buttons.append(button)

    def _callback_with_lock(self, callback: Callable):
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
        self.add_points(points)     # mode="points"
        
    def register_algorithm(self, name: str, algo: Callable[[list[Point]], list[Point]]):
        self.register_button(name, lambda _: self._algorithm_callback(algo))

    def _algorithm_callback(self, algo):
        self.clear_background()
        start = time.time()
        result = algo(self.points)
        end = time.time()
        self.add_polygon(result)    # mode="polygon"
        self.label.value = f"Runtime: {1000 * (end - start)} ms"
    
    def clear(self):
        self.clear_background()
        self.clear_points()

    def clear_background(self):
        self.canvas[0].clear()

    def clear_points(self):
        self.points.clear()
        self.canvas[1].clear()

    def display(self):
        display(self.canvas)
        display(HBox(self.buttons))
        display(self.label)
