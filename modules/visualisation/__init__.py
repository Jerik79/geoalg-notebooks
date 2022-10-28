from collections import deque
from itertools import chain
from typing import Callable, Iterable, Optional, Type
import time

from geometry import Point
from .drawing import AppendEvent, DrawingMode, InstanceDrawer, AlgorithmDrawer
from .drawing import PointsMode, SweepLineMode, PathMode, PolygonMode, FixedVertexNumberPathsMode, LineSegmentsMode

from ipycanvas import MultiCanvas
from ipywidgets import Output, Button, Label, Checkbox, HBox, VBox, IntSlider, Layout, HTML, dlink, Widget, BoundedIntText
from IPython.display import display, display_html
import numpy as np


class Visualisation:
    ## Constants.

    _DEFAULT_VBOX_ITEM_MARGIN = "0px 0px 20px 0px"

    _INSTANCE_BACK = 0
    _ALGORITHM_BACK = 1
    _INSTANCE_MAIN = 2
    _ALGORITHM_MAIN = 3
    _INSTANCE_FRONT = 4
    _ALGORITHM_FRONT = 5
    _INSTANCE_HIGHLIGHT = 6
    _ALGORITHM_HIGHLIGHT = 7


    ## Initialisation methods.

    def __init__(self, width: int, height: int, instance_type: Type, instance_mode: DrawingMode):
        self._width = width
        self._height = height

        self._current_instance = set()
        self._point_buffer = deque()
        self._point_counter = 0

        if not hasattr(instance_type, "add_point_to_instance"):
            raise ValueError("Instance type is not supported.")
        self._instance_type = instance_type

        self._init_canvas(instance_mode)
        self._init_ui()

    def _init_canvas(self, instance_mode: DrawingMode):
        self._multi_canvas = MultiCanvas(8, width = self._width, height = self._height)
        for i in range(0, 8):
            self._multi_canvas[i].translate(0, self._height)
            self._multi_canvas[i].scale(1, -1)

        self._instance_drawer = InstanceDrawer(
            instance_mode,
            self._multi_canvas[self._INSTANCE_BACK],
            self._multi_canvas[self._INSTANCE_MAIN],
            self._multi_canvas[self._INSTANCE_FRONT],
            self._multi_canvas[self._INSTANCE_HIGHLIGHT]
        )
        self._algorithm_drawer = None

        self._previous_callback_finish_time = time.time()
        def handle_click_on_canvas(x, y):
            if time.time() - self._previous_callback_finish_time < 1:       # TODO: This doesn't work well...
                return
            if self.add_point(Point(x, self._height - y)):
                self.clear_algorithm_output()
                self._clear_time_labels()
        self._multi_canvas.on_mouse_down(handle_click_on_canvas)

        self._canvas_output = Output(layout = Layout(border = "1px solid black"))
        with self._canvas_output:
            display(self._multi_canvas)

    def _init_ui(self):
        self._instance_size_label = Label()
        self._update_instance_size_label()

        self._clear_canvas_button = self._create_button("Clear canvas", self.clear)

        self._random_button_int_text = BoundedIntText(
            value = 250,        # TODO: Maybe make this configurable (or dependent on instance type).
            min = 1,
            max = 999,
            layout = Layout(width = "55px")
        )
        def get_random_value(maximum: int) -> np.float64:       # TODO: Maybe make this configurable (or dependent on instance type).
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

        self._example_buttons = []
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


    ## Properties.

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def _activatable_widgets(self) -> Iterable[Widget]:
        return (
            self._clear_canvas_button,
            self._random_button_int_text, self._random_button,
            *self._example_buttons, *self._algorithm_buttons,
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
            vbox_with_header("Examples", self._example_buttons),
            vbox_with_header("Algorithms", self._algorithm_buttons),
            vbox_with_header("Times", self._time_labels, right_aligned = True)
        ])

        display(
            HBox([
                VBox([self._canvas_output, self._instance_size_label]),
                VBox([upper_ui_widget_row, lower_ui_widget_row])
            ], layout = Layout(justify_content = "space-around"))
        )

    """ def display(self, number = [2]):
        display_html(f"<img style='float: left;' src='../images/convex-hull-{number[0]}.png'>", raw = True)
        number[0] += 1 """

    def add_point(self, point: Point) -> bool:
        if self._point_counter >= 999:
            return False
        needs_draw = self._instance_type.add_point_to_instance(self._current_instance, self._point_buffer, point)
        if needs_draw:
            self._instance_drawer.draw((point,))
            self._point_counter += 1
            self._update_instance_size_label()
        return needs_draw

    def add_points(self, points: Iterable[Point]):
        points_to_draw = []
        for point in points:
            if self._point_counter >= 999:
                break
            if self._instance_type.add_point_to_instance(self._current_instance, self._point_buffer, point):
                points_to_draw.append(point)
                self._point_counter += 1
        self._instance_drawer.draw(points_to_draw)
        self._update_instance_size_label()

    def _update_instance_size_label(self):
        label_value = f"Instance size: {len(self._current_instance):0>3}"
        if self._point_counter != len(self._current_instance):
            label_value += f" (Number of points: {self._point_counter:0>3})"
        self._instance_size_label.value = label_value

    def clear(self):
        self.clear_current_instance()
        self.clear_algorithm_output()
        self._clear_time_labels()

    def clear_algorithm_output(self):
        if self._algorithm_drawer is not None:
            self._algorithm_drawer.clear()

    def clear_current_instance(self):
        self._current_instance.clear()
        self._point_buffer.clear()
        self._instance_drawer.clear()
        self._point_counter = 0
        self._update_instance_size_label()

    def _clear_time_labels(self):
        for label in self._time_labels:
            label.value = ""

    def register_example_instance(self, name: str, instance: set):
        instance_points = list(chain.from_iterable(element.points() for element in instance))
        def instance_callback():
            self.clear()
            self.add_points(instance_points)
        self._example_buttons.append(self._create_button(name, instance_callback))

    def register_algorithm(self, name: str, algorithm: Callable, drawing_mode: DrawingMode):
        algorithm_drawer = AlgorithmDrawer(
            drawing_mode,
            self._multi_canvas[self._ALGORITHM_BACK],
            self._multi_canvas[self._ALGORITHM_MAIN],
            self._multi_canvas[self._ALGORITHM_FRONT],
            self._multi_canvas[self._ALGORITHM_HIGHLIGHT]
        )
        label_index = len(self._time_labels)
        self._time_labels.append(Label(layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN)))
        def algorithm_callback():
            self.clear_algorithm_output()
            self._time_labels[label_index].value = "RUNNING"        # TODO: Refine this.
            start_time = time.time()
            try:
                algorithm_output = algorithm(self._current_instance)
            except:
                self._time_labels[label_index].value = "ERROR"
                return
            end_time = time.time()
            if not self._animation_checkbox.value:
                algorithm_drawer.draw(algorithm_output.points())
            else:
                self._time_labels[label_index].value = "ANIMATING"
                animation_time_step = 1.1 - 0.1 * self._animation_speed_slider.value
                if hasattr(algorithm_output, "animation_events"):
                    animation_events = algorithm_output.animation_events()
                else:
                    animation_events = (AppendEvent(point) for point in algorithm_output.points())
                algorithm_drawer.animate(animation_events, animation_time_step)
            self._time_labels[label_index].value = f"{1000 * (end_time - start_time):.3f} ms"
            self._algorithm_drawer = algorithm_drawer
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
