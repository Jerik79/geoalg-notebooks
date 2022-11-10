from typing import Callable, Generic, TypeVar, Optional, Iterable
import time

from geometry import Point
from .instances import Algorithm, InstanceHandle
from .drawing import CanvasDrawingHandle, DrawingMode, Drawer

from ipycanvas import MultiCanvas
from ipywidgets import Output, Button, Checkbox, HBox, VBox, IntSlider, Layout, HTML, dlink, Widget, BoundedIntText
from IPython.display import display, display_html


T = TypeVar("T")

class VisualisationTool(Generic[T]):
    ## Constants.

    _DEFAULT_VBOX_ITEM_MARGIN = "0px 0px 20px 0px"

    _INSTANCE_BACK = 0
    _ALGORITHM_BACK = 1
    _INSTANCE_MAIN = 2
    _ALGORITHM_MAIN = 3
    _INSTANCE_FRONT = 4
    _ALGORITHM_FRONT = 5


    ## Initialisation methods.

    def __init__(self, width: int, height: int, instance: InstanceHandle[T]):
        self._width = width
        self._height = height

        self._instance = instance
        self._number_of_points = 0

        self._multi_canvas = MultiCanvas(6, width = self._width, height = self._height)
        self._init_canvases()

        self._previous_callback_finish_time = time.time()
        def handle_click_on_canvas(x, y):
            if time.time() - self._previous_callback_finish_time < 1:       # TODO: This doesn't work well...
                return
            if self.add_point(Point(x, self._height - y)):
                self.clear_algorithm_output()
                self._clear_message_labels()
        self._multi_canvas.on_mouse_down(handle_click_on_canvas)

        self._canvas_output = Output(layout = Layout(border = "1px solid black"))
        with self._canvas_output:
            display(self._multi_canvas)

        self._init_ui()

    def _init_canvases(self):
        for i in range(0, 6):
            self._multi_canvas[i].translate(0, self._height)
            self._multi_canvas[i].scale(1, -1)
            if i != 5:
                self._multi_canvas[i].line_width = 2

        ib_canvas = CanvasDrawingHandle(self._multi_canvas[self._INSTANCE_BACK])
        im_canvas = CanvasDrawingHandle(self._multi_canvas[self._INSTANCE_MAIN])
        if_canvas = CanvasDrawingHandle(self._multi_canvas[self._INSTANCE_FRONT])
        for canvas in (ib_canvas, im_canvas, if_canvas):
            canvas.set_colour(255, 165, 0)
        self._instance_drawer = Drawer(self._instance.drawing_mode, ib_canvas, im_canvas, if_canvas)

        self._ab_canvas = CanvasDrawingHandle(self._multi_canvas[self._ALGORITHM_BACK])
        self._am_canvas = CanvasDrawingHandle(self._multi_canvas[self._ALGORITHM_MAIN])
        self._af_canvas = CanvasDrawingHandle(self._multi_canvas[self._ALGORITHM_FRONT])
        for canvas in (self._ab_canvas, self._am_canvas):
            canvas.set_colour(0, 0, 255)
        self._af_canvas.set_colour(0, 0, 0)
        self._current_algorithm_drawer = None

    def _init_ui(self):
        self._instance_size_label = HTML()
        self._update_instance_size_label()

        self._clear_button = self._create_button("Clear", self.clear)

        self._random_button_int_text = BoundedIntText(
            value = self._instance.default_number_of_random_points,
            min = 1,
            max = 999,
            layout = Layout(width = "55px")
        )
        def random_button_callback():
            self.clear()
            self.add_points([
                Point(
                    self._instance.get_random_coordinate(self._width),
                    self._instance.get_random_coordinate(self._height)
                ) for _ in range(self._random_button_int_text.value)
            ])
        self._random_button = self._create_button(
            "Random",
            random_button_callback,
            layout = Layout(width = "85px", margin = "2px 5px 0px 1px")
        )

        self._init_animation_ui()

        self._example_buttons = []
        self._algorithm_buttons = []
        self._message_labels = []

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
            self._clear_button,
            self._random_button_int_text, self._random_button,
            self._animation_checkbox, self._animation_speed_slider,
            *self._example_buttons, *self._algorithm_buttons
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
            vbox_with_header("Canvas", (self._clear_button, random_button_hbox)),
            vbox_with_header("Animation", (self._animation_checkbox, self._animation_speed_slider)),
        ], layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN))

        lower_ui_widget_row = HBox([
            vbox_with_header("Examples", self._example_buttons),
            vbox_with_header("Algorithms", self._algorithm_buttons),
            vbox_with_header("Messages", self._message_labels, right_aligned = True)
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
        if self._number_of_points >= 999:
            return False
        needs_draw = self._instance.add_point(point)
        if needs_draw:
            self._instance_drawer.draw((point,))
            self._number_of_points += 1
            self._update_instance_size_label()
        return needs_draw

    def add_points(self, points: Iterable[Point]):
        points_to_draw = []
        for point in points:
            if self._number_of_points >= 999:
                break
            if self._instance.add_point(point):
                points_to_draw.append(point)
                self._number_of_points += 1
        self._instance_drawer.draw(points_to_draw)
        self._update_instance_size_label()

    def _update_instance_size_label(self):
        label_value = f"Instance size: {len(self._instance):0>3}"
        if self._number_of_points != len(self._instance):
            label_value += f" (Number of points: {self._number_of_points:0>3})"
        self._instance_size_label.value = label_value

    def clear(self):
        self.clear_instance()
        self.clear_algorithm_output()
        self._clear_message_labels()

    def clear_instance(self):
        self._instance.clear()
        self._instance_drawer.clear()
        self._number_of_points = 0
        self._update_instance_size_label()

    def clear_algorithm_output(self):
        if self._current_algorithm_drawer is not None:
            self._current_algorithm_drawer.clear()

    def _clear_message_labels(self):
        for label in self._message_labels:
            label.value = "<br>"

    def register_example_instance(self, name: str, instance: T):
        example_instance_points = self._instance.extract_points_from_raw_instance(instance)
        def example_instance_callback():
            self.clear()
            self.add_points(example_instance_points)
        self._example_buttons.append(self._create_button(name, example_instance_callback))

    def register_algorithm(self, name: str, algorithm: Algorithm[T], drawing_mode: DrawingMode):
        algorithm_drawer = Drawer(drawing_mode, self._ab_canvas, self._am_canvas, self._af_canvas)
        label_index = len(self._message_labels)
        self._message_labels.append(HTML(value = "<br>", layout = Layout(margin = self._DEFAULT_VBOX_ITEM_MARGIN)))
        def algorithm_callback():
            self.clear_algorithm_output()
            self._message_labels[label_index].value = "RUNNING"
            try:
                algorithm_output, algorithm_running_time = self._instance.run_algorithm(algorithm)
            except:
                self._message_labels[label_index].value = "<b><font color='red'>ERROR</font></b>"
                return
            if not self._animation_checkbox.value:
                algorithm_drawer.draw(algorithm_output.points())
            else:
                self._message_labels[label_index].value = "ANIMATING"
                animation_time_step = 1.1 - 0.1 * self._animation_speed_slider.value
                algorithm_drawer.animate(algorithm_output.animation_events(), animation_time_step)
            self._message_labels[label_index].value = f"{algorithm_running_time:.3f} ms"
            self._current_algorithm_drawer = algorithm_drawer
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
