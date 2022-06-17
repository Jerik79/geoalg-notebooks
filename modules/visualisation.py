from enum import Enum, auto
from typing import Callable, Iterable, Optional
from ipycanvas import MultiCanvas, hold_canvas
from ipywidgets import Output, Button, Label, Checkbox, HBox, VBox, IntSlider, Layout, HTML, dlink, Widget, BoundedIntText
from IPython.display import display
from geometry import Point, Polygon, AppendEvent
import time
import numpy as np

# Canvas numbers for background, points and highlighting.
BG = 0
PTS = 1
HL = 2

class DrawingMode(Enum):        # TODO: Isn't used yet...
    Points = auto()
    Path = auto()
    Polygon = auto()


class Visualisation:
    def __init__(self, width: int = 500, height: int = 500):
        self._width = width
        self._height = height

        self._points = set()
        self._animation_was_started = False
        self._canvas_output = Output(layout = Layout(border = "1px solid black"))

        self._previous_callback_finish_time = time.time()
        def handle_click_on_canvas(x, y):
            if time.time() - self._previous_callback_finish_time < 0.35:
                return
            if self.add_points([Point(x, self._height - y)]):
                self.clear_background()
                self._clear_runtime_labels()
        self._handle_click_on_canvas = handle_click_on_canvas

        self._init_canvas()
        self._init_ui()


    # Initialisation methods.

    def _init_canvas(self) -> MultiCanvas:
        canvas = MultiCanvas(3, width = self._width, height = self._height)
        canvas.on_mouse_down(self._handle_click_on_canvas)

        canvas[BG].line_width = 2
        canvas[BG].stroke_style = "blue"
        canvas[BG].fill_style = "rgba(0, 0, 255, 0.2)"

        canvas[PTS].stroke_style = "orange"
        canvas[PTS].fill_style = "orange"

        canvas[HL].stroke_style = "black"            # TODO: own mode for each layer?
        canvas[HL].fill_style = "rgba(0, 0, 0, 0.2)"

        for cv in range(0, 3):
            canvas[cv].translate(0, self._height)
            canvas[cv].scale(1, -1)

        self._canvas = canvas
        self.draw_points(self._points)

        self._canvas_output.clear_output(wait = True)
        with self._canvas_output:
            display(self._canvas)

    def _init_ui(self):
        self._number_label = Label()
        self._update_number_label()

        self._default_vbox_item_margin = "0px 0px 20px 0px"
        self._clear_canvas_button = self._create_button("Clear canvas", self.clear)

        self._random_button_int_text = BoundedIntText(
            value = 250,
            min = 1,
            max = 999,
            layout = Layout(width = "55px")
        )
        def get_random_value(maximum: int) -> int:
            return np.clip(np.random.normal(0.5 * maximum, 0.15 * maximum), 0, maximum)
        def random_button_callback():
            self.clear()
            self.add_points([       # TODO: mode
                Point(get_random_value(self._width), get_random_value(self._height))
                for _ in range(self._random_button_int_text.value)
            ])
        self._random_button = self._create_button(
            "Random",
            random_button_callback,
            layout = Layout(width = "85px", margin = "2px 5px 0px 1px")
        )

        self._init_animation_ui()

        self._instance_buttons = []
        self._algorithm_buttons = []
        self._runtime_labels = []

    def _init_animation_ui(self):
        self._animation_checkbox = Checkbox(
            value = False,
            description = "Animate",
            indent = False,
            layout = Layout(margin = self._default_vbox_item_margin)
        )
        self._animation_speed_slider = IntSlider(
            value = 5,
            min = 1,
            max = 10,
            description = "Speed",
        )
        self._slider_visibility_link = dlink(
            (self._animation_checkbox, "value"),
            (self._animation_speed_slider.layout, "visibility"),
            transform = lambda value: "visible" if value else "hidden"
        )
        self._slider_activity_link = dlink(
            (self._animation_speed_slider, "disabled"),
            (self._animation_speed_slider.layout, "border"),
            transform = lambda disabled: "1px solid lightgrey" if disabled else "1px solid black"
        )

    @property
    def _activatable_widgets(self) -> Iterable[Widget]:
        return (
            self._clear_canvas_button,
            self._random_button_int_text, self._random_button,
            *self._instance_buttons, *self._algorithm_buttons,
            self._animation_checkbox, self._animation_speed_slider
        )


    # Widget display and manipulation methods.

    def display(self):
        def vbox_with_header(title: str, children: Iterable[Widget], right_aligned: bool = False) -> VBox:
            header = HTML(f"<h2>{title}</h2>", layout = Layout(align_self = "flex-start"))
            vbox_layout = Layout(padding = "0px 25px", align_items = "flex-start")
            if right_aligned:
                vbox_layout.align_items = "flex-end"
            return VBox([header, *children], layout = vbox_layout)

        random_button_hbox = HBox([self._random_button, self._random_button_int_text])
        upper_ui_widget_row = HBox([
            vbox_with_header("Canvas", (self._clear_canvas_button, random_button_hbox)),
            vbox_with_header("Animation", (self._animation_checkbox, self._animation_speed_slider)),
        ], layout = Layout(margin = self._default_vbox_item_margin))

        lower_ui_widget_row = HBox([
            vbox_with_header("Instances", self._instance_buttons),
            vbox_with_header("Algorithms", self._algorithm_buttons),
            vbox_with_header("Runtimes", self._runtime_labels, right_aligned = True)
        ])

        display(
            HBox([
                VBox([self._canvas_output, self._number_label]),
                VBox([upper_ui_widget_row, lower_ui_widget_row])
            ], layout = Layout(justify_content = "space-around"))
        )

    def _disable_widgets(self):
        for widget in self._activatable_widgets:
            widget.disabled = True

    def _enable_widgets(self):
        for widget in self._activatable_widgets:
            widget.disabled = False

    def _create_button(self, description: str, callback: Callable, layout: Optional[Layout] = None) -> Button:
        if layout is None:
            layout = Layout(margin = self._default_vbox_item_margin)
        button = Button(description = description, layout = layout)
        def button_callback(_: Button):
            self._disable_widgets()
            callback()
            self._enable_widgets()
            self._previous_callback_finish_time = time.time()
        button.on_click(button_callback)
        return button

    def _update_number_label(self):
        self._number_label.value = f"Number of points: {len(self._points):0>3}"

    def _clear_runtime_labels(self):
        for label in self._runtime_labels:
            label.value = ""


    # Public registering methods.

    def register_instance(self, name: str, points: list[Point]):
        def instance_callback():
            self.clear()
            self.add_points(points)     # TODO: mode="points"
        self._instance_buttons.append(self._create_button(name, instance_callback))
        
    def register_algorithm(self, name: str, algorithm: Callable):
        label_index = len(self._runtime_labels)
        def algorithm_callback():
            self.clear_background()
            start = time.time()
            result = algorithm(self._points)
            end = time.time()
            self.draw_polygon(result, animate = self._animation_checkbox.value)     # TODO: mode="polygon"
            self._runtime_labels[label_index].value = f"{1000 * (end - start):.3f} ms"

        self._runtime_labels.append(Label(layout = Layout(margin = self._default_vbox_item_margin)))
        self._algorithm_buttons.append(self._create_button(name, algorithm_callback))


    # Point and clear stuff

    def add_points(self, points: list[Point]) -> bool:      # TODO: modes !!!
        union = self._points.union(set(points))
        if len(union) > 999:
            return False
        self._points = union
        self.draw_points(points)
        self._update_number_label()
        return True

    def clear(self):
        self.clear_points()
        self.clear_background()
        self._clear_runtime_labels()

    def clear_background(self):
        self._canvas[BG].clear()
        if self._animation_was_started:
            self._animation_was_started = False
            self._init_canvas()

    def clear_points(self):
        self._points.clear()
        self._canvas[PTS].clear()
        self._update_number_label()


    # Draw stuff

    def draw_point(self, point: Point):         # TODO: make some of this private?
        self._canvas[PTS].fill_circle(point.x, point.y, 5)

    def draw_points(self, points: Iterable[Point]):
        with hold_canvas(self._canvas[PTS]):
            for point in points:
                self.draw_point(point)

    def draw_path(self, cv: int, points: list[Point], close=False, fill=False):
        if points:
            self._canvas[cv].begin_path()
            self._canvas[cv].move_to(points[0].x, points[0].y)
            for point in points[1:]:
                self._canvas[cv].line_to(point.x, point.y)
            if close:
                self._canvas[cv].close_path()
            self._canvas[cv].stroke()
            if fill:
                self._canvas[cv].fill()

    def draw_polygon(self, polygon: Polygon, animate=False):
        with hold_canvas(self._canvas[BG]), hold_canvas(self._canvas[HL]):
            if animate:
                if polygon.points:
                    polygon.append(polygon.points[0])
                current_points = []
                background_points = []
                self._animation_was_started = True
                step_time = 1100 - 100 * self._animation_speed_slider.value
                for event in polygon.events:
                    if isinstance(event, AppendEvent) and current_points and event.point == current_points[-1]:
                        continue

                    background_points.clear()
                    event.execute_on(current_points, background_points)

                    if background_points:
                        self._canvas[HL].clear()
                        self.draw_path(HL, background_points, close=True)
                        self._canvas[HL].sleep(2 * step_time)
                        self._canvas[BG].sleep(step_time)
                    else:
                        self._canvas[HL].sleep(step_time)

                    self._canvas[BG].clear()
                    self.draw_path(BG, current_points)
                    self._canvas[BG].fill_circle(current_points[-1].x, current_points[-1].y, 10)
                    self._canvas[BG].sleep(step_time)
                self._canvas[BG].clear()
                self._canvas[HL].clear()
            self.draw_path(BG, polygon.points, close=True, fill=True)
    
