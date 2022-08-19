from enum import Enum, auto
from typing import Callable, Iterable, Optional
from ipycanvas import MultiCanvas, hold_canvas
from ipywidgets import Output, Button, Label, Checkbox, HBox, VBox, IntSlider, Layout, HTML, dlink, Widget, BoundedIntText
from IPython.display import display, display_html, Image, Markdown
from geometry import Point, Polygon, AppendEvent
import time
import numpy as np


# TODO: Not used yet. Give each layer drawing mode. The modes should be selected at the time of object initialisation.
class DrawingMode(Enum):
    Points = auto()
    Path = auto()
    Polygon = auto()


class Layer(Enum):
    _ALGO_BACK = 0       # Background used for algorithm outputs.
    _PTS_MAIN = 1       # Main layer used for points / instances.
    _ALGO_MAIN = 2       # Foreground used for additional highlights during animations.
    _PTS_FORE = 3
    _ALGO_FORE = 4
    _FRONT = 5


class Visualisation:
    ## Constants.

    _DEFAULT_POINT_RADIUS = 5
    _DEFAULT_VBOX_ITEM_MARGIN = "0px 0px 20px 0px"


    ## Initialisation methods.

    def __init__(self, width, height):
        self._width = width
        self._height = height

        self._points = set()
        self._canvas_output = Output(layout = Layout(border = "1px solid black"))

        self._previous_callback_finish_time = time.time()
        def handle_click_on_canvas(x, y):
            if time.time() - self._previous_callback_finish_time < 1:       # TODO: This doesn't work well...
                return
            if self.add_point(Point(x, self._height - y)):
                self.clear_algorithm_layers()
                self._clear_time_labels()
        self._handle_click_on_canvas = handle_click_on_canvas

        self._init_canvas()
        self._init_ui()

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def _init_canvas(self) -> MultiCanvas:
        canvas = MultiCanvas(6, width = self._width, height = self._height)
        canvas.on_mouse_down(self._handle_click_on_canvas)

        for pts_layer in (Layer._PTS_MAIN, Layer._PTS_FORE):
            canvas[pts_layer.value].stroke_style = "orange"
            canvas[pts_layer.value].fill_style = "orange"

        for algo_layer in (Layer._ALGO_BACK, Layer._ALGO_MAIN, Layer._ALGO_FORE):
            canvas[algo_layer.value].line_width = 2
            canvas[algo_layer.value].stroke_style = "blue"
            canvas[algo_layer.value].fill_style = "rgba(0, 0, 255, 0.2)"

        canvas[Layer._FRONT.value].stroke_style = "black"
        canvas[Layer._FRONT.value].fill_style = "rgba(0, 0, 0, 0.2)"

        for value in map(lambda layer: layer.value, Layer):
            canvas[value].translate(0, self._height)
            canvas[value].scale(1, -1)

        self._canvas = canvas
        self.draw_points(self._points)

        self._canvas_output.clear_output(wait = True)
        with self._canvas_output:
            display(self._canvas)

    def _init_ui(self):
        self._point_number_label = Label()
        self._update_point_number_label()

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
            self.add_points([
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
        self._time_labels = []

    def _init_animation_ui(self):
        self._animation_checkbox = Checkbox(
            value = False,
            description = "Animate",
            indent = False,
            layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN)
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


    ## Widget display and manipulation methods.

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
        ], layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN))

        lower_ui_widget_row = HBox([
            vbox_with_header("Instances", self._instance_buttons),
            vbox_with_header("Algorithms", self._algorithm_buttons),
            vbox_with_header("Times", self._time_labels, right_aligned = True)
        ])

        display(
            HBox([
                VBox([self._canvas_output, self._point_number_label]),
                VBox([upper_ui_widget_row, lower_ui_widget_row])
            ], layout = Layout(justify_content = "space-around"))
        )

    """ def display(self, number = [2]):
        display_html(f"<img style='float: left;' src='../images/convex-hull-{number[0]}.png'>", raw = True)
        number[0] += 1 """

    # TODO: Respect drawing modes.
    def add_point(self, point: Point, radius: int = _DEFAULT_POINT_RADIUS) -> bool:
        if len(self._points) >= 999 or point in self._points:
            return False
        self._points.add(point)
        self.draw_point(point, radius = radius, layer = Layer._PTS_MAIN)
        self._update_point_number_label()
        return True

    # TODO: Respect drawing modes.
    def add_points(self, points: Iterable[Point], radius: int = _DEFAULT_POINT_RADIUS):
        with hold_canvas(self._canvas[Layer._PTS_MAIN.value]):
            for point in points:
                if len(self._points) >= 999:
                    break
                if point in self._points:
                    continue
                self._points.add(point)
                self.draw_point(point, radius = radius, layer = Layer._PTS_MAIN)
        self._update_point_number_label()

    def _update_point_number_label(self):
        self._point_number_label.value = f"Number of points: {len(self._points):0>3}"

    def clear(self):
        self.clear_point_layers()
        self.clear_algorithm_layers()
        self._clear_time_labels()

    def clear_algorithm_layers(self):
        self._canvas[Layer._ALGO_BACK.value].clear()
        self._canvas[Layer._ALGO_MAIN.value].clear()
        self._canvas[Layer._ALGO_FORE.value].clear()
        self._canvas[Layer._PTS_FORE.value].clear()
        self._canvas[Layer._FRONT.value].clear()

    def clear_point_layers(self):
        self._points.clear()
        self._canvas[Layer._PTS_MAIN.value].clear()
        self._canvas[Layer._PTS_FORE.value].clear()
        self._update_point_number_label()

    def _clear_time_labels(self):
        for label in self._time_labels:
            label.value = ""

    def register_instance(self, name: str, points: Iterable[Point]):
        def instance_callback():
            self.clear()
            self.add_points(points)
        self._instance_buttons.append(self._create_button(name, instance_callback))

    # TODO: Respect drawing modes.
    def register_algorithm(self, name: str, algorithm: Callable):
        label_index = len(self._time_labels)
        self._time_labels.append(Label(layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN)))
        def algorithm_callback():
            self.clear_algorithm_layers()
            start_time = time.time()
            result = algorithm(self._points)
            end_time = time.time()
            self.draw_polygon(result, animate = self._animation_checkbox.value)
            self._time_labels[label_index].value = f"{1000 * (end_time - start_time):.3f} ms"
        self._algorithm_buttons.append(self._create_button(name, algorithm_callback))

    def _create_button(self, description: str, callback: Callable, layout: Optional[Layout] = None) -> Button:
        if layout is None:
            layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN)
        button = Button(description = description, layout = layout)
        def button_callback(_: Button):
            self._disable_widgets()
            callback()
            self._enable_widgets()
            self._previous_callback_finish_time = time.time()
        button.on_click(button_callback)
        return button

    def _disable_widgets(self):
        for widget in self._activatable_widgets:
            widget.disabled = True

    def _enable_widgets(self):
        for widget in self._activatable_widgets:
            widget.disabled = False


    ## Canvas drawing methods.

    # TODO: Respect drawing modes.
    def draw_point(self, point: Point, radius: int = _DEFAULT_POINT_RADIUS, layer: Layer = Layer._PTS_MAIN):
        self._canvas[layer.value].fill_circle(point.x, point.y, radius)

    # TODO: Respect drawing modes.
    def draw_points(self, points: Iterable[Point], radius: int = _DEFAULT_POINT_RADIUS, layer: Layer = Layer._PTS_MAIN):
        with hold_canvas(self._canvas[layer.value]):
            for point in points:
                self.draw_point(point, radius = radius, layer = layer)

    # TODO: Respect drawing modes. Generalise 'background_points' and foreground drawings. Maybe make layer(s) selectable.
    def draw_polygon(self, polygon: Polygon, animate = False):
        if animate:
            if polygon.points:
                polygon.append(polygon.points[0])

            current_points = []
            background_points = []
            step_time = 1.1 - 0.1 * self._animation_speed_slider.value

            for event in polygon.events:
                if isinstance(event, AppendEvent) and current_points and event.point == current_points[-1]:
                    continue

                background_points.clear()
                event.execute_on(current_points, background_points)

                if background_points:
                    with hold_canvas(self._canvas[Layer._FRONT.value]):
                        self._canvas[Layer._FRONT.value].clear()
                        self._draw_static_path(background_points, Layer._FRONT, close = True)
                    time.sleep(step_time)

                with hold_canvas(self._canvas[Layer._PTS_FORE.value]), hold_canvas(self._canvas[Layer._ALGO_MAIN.value]):
                    self._canvas[Layer._PTS_FORE.value].clear()
                    self._canvas[Layer._ALGO_MAIN.value].clear()
                    for point in current_points[:-1]:
                        self.draw_point(point, layer = Layer._PTS_FORE)
                        self._canvas[Layer._ALGO_MAIN.value].stroke_circle(point.x, point.y, 6)
                    self.draw_point(current_points[-1], layer = Layer._PTS_FORE)
                    self.draw_point(current_points[-1], radius = 12, layer = Layer._ALGO_MAIN)
                    self._draw_static_path(current_points, Layer._ALGO_MAIN)
                time.sleep(step_time)

            self._canvas[Layer._FRONT.value].clear()
            self._canvas[Layer._PTS_FORE.value].clear()
            self._canvas[Layer._ALGO_MAIN.value].clear()

        with hold_canvas(self._canvas[Layer._PTS_FORE.value]), hold_canvas(self._canvas[Layer._ALGO_MAIN.value]), \
        hold_canvas(self._canvas[Layer._ALGO_BACK.value]):
            for point in polygon.points:
                self.draw_point(point, layer = Layer._PTS_FORE)
                self._canvas[Layer._ALGO_MAIN.value].stroke_circle(point.x, point.y, 6)
            self._draw_static_path(polygon.points, Layer._ALGO_MAIN, close = True)
            self._draw_static_path(polygon.points, Layer._ALGO_BACK, close = True, stroke = False, fill = True)


    def _draw_static_path(self, points: Iterable[Point], layer: Layer, close = False, stroke = True, fill = False):
        points_iterator = iter(points)
        first_point = next(points_iterator)
        self._canvas[layer.value].begin_path()
        self._canvas[layer.value].move_to(first_point.x, first_point.y)
        for point in points_iterator:
            self._canvas[layer.value].line_to(point.x, point.y)
        if close:
            self._canvas[layer.value].close_path()
        if stroke:
            self._canvas[layer.value].stroke()
        if fill:
            self._canvas[layer.value].fill()

    # TODO:  Add Path type that can be animated like Polygon.
    """ def draw_path(self, points: Path, layer: Layer, animate = False):
        if not animate:
            self._draw_static_path(points, layer)
        else:
            pass """
