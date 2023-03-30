import html
import time
from typing import Callable, Generic, Iterable, Optional

from ..geometry.core import Point
from .drawing import CanvasDrawingHandle, Drawer, DrawingMode
from .instances import Algorithm, I, InstanceHandle

from ipycanvas import MultiCanvas
from ipywidgets import (
    BoundedIntText, Button, ButtonStyle, Checkbox, dlink,
    GridBox, HBox, HTML, Layout, Output, VBox, Widget
)
from IPython.display import display, display_html


class VisualisationTool(Generic[I]):
    ## Constants.

    _MAX_NUMBER_OF_POINTS = 999
    _DEFAULT_ITEM_WIDTH = "150px"

    _INSTANCE_BACK = 0
    _ALGORITHM_BACK = 1
    _INSTANCE_MAIN = 2
    _ALGORITHM_MAIN = 3
    _INSTANCE_FRONT = 4
    _ALGORITHM_FRONT = 5


    ## Initialisation methods.

    def __init__(self, width: int, height: int, instance: InstanceHandle[I], notebook_number: Optional[int] = None):
        self._width = width
        self._height = height

        self._instance = instance
        self._number_of_points: int = 0

        self._notebook_number = notebook_number
        self._next_image_number: int = 1

        self._previous_callback_finish_time: float = time.time()
        def handle_click_on_multi_canvas(x: float, y: float):
            if time.time() - self._previous_callback_finish_time < 1.0:       # TODO: This doesn't work well...
                return
            if self.add_point(Point(x, self._height - y)):
                self.clear_algorithm_drawings()
                self.clear_algorithm_messages()

        self._multi_canvas = MultiCanvas(6, width = self._width, height = self._height)
        self._multi_canvas.on_mouse_down(handle_click_on_multi_canvas)
        self._canvas_output = Output(layout = Layout(border = "1px solid black"))
        with self._canvas_output:
            display(self._multi_canvas)

        self._init_canvases()
        self._init_ui()

    def _init_canvases(self):
        for i in range(0, 6):
            self._multi_canvas[i].translate(0, self._height)
            self._multi_canvas[i].scale(1, -1)
            self._multi_canvas[i].line_cap = "round"
            self._multi_canvas[i].line_join = "round"
            if i != 5:
                self._multi_canvas[i].line_width = 3        # TODO: This could be a parameter of CanvasDrawingHandle.draw_path(...).

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
        self._current_algorithm_drawer: Optional[Drawer] = None

    def _init_ui(self):
        self._instance_size_info = HTML()
        self._update_instance_size_info()

        self._clear_button = self._create_button("Clear", self.clear)
        self._example_buttons: list[Button] = []
        self._algorithm_buttons: list[Button] = []
        self._algorithm_messages: list[HTML] = []

        self._init_random_ui()
        self._init_animation_ui()

    def _init_random_ui(self):
        self._random_number_int_text = BoundedIntText(
            value = self._instance.default_number_of_random_points,
            min = 1,
            max = self._MAX_NUMBER_OF_POINTS,
            layout = Layout(width = "60px")
        )
        self._random_number_hbox = HBox(
            [HTML("Points:"), self._random_number_int_text],
            layout = Layout(width = self._DEFAULT_ITEM_WIDTH)
        )

        self._random_message = HTML("<br>")
        def random_button_callback():
            self.clear()
            self._random_message.value = "<b>GENERATING</b>"
            self.add_points(self._instance.generate_random_points(
                self._width, self._height, self._random_number_int_text.value
            ))
            self._random_message.value = "<br>"

        self._random_button = self._create_button("Random", random_button_callback)

    def _init_animation_ui(self):
        self._animation_checkbox = Checkbox(
            value = False,
            description = "Animations",
            indent = False,
            layout = Layout(width = self._DEFAULT_ITEM_WIDTH)
        )

        self._animation_speed_int_text = BoundedIntText(
            value = 5,
            min = 1,
            max = 10,
            layout = Layout(width = "50px")
        )
        self._animation_speed_hbox = HBox([HTML("Speed:"), self._animation_speed_int_text])

        self._animation_speed_visibility_link = dlink(
            (self._animation_checkbox, "value"),
            (self._animation_speed_hbox.layout, "visibility"),
            transform = lambda value: "visible" if value else "hidden"
        )


    ## Properties.

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height


    ## Widget display and manipulation methods.

    def display(self):
        if self._notebook_number is not None:
            # Redudantly convert attributes to integers. This fails in case of a potential HTML injection.
            image_filename = f"{int(self._notebook_number):0>2}-image{int(self._next_image_number):0>2}.png"
            display_html(f"<img style='float: left;' src='./images/{image_filename}'>", raw = True)
            self._next_image_number += 1
            return

        ui_grid_layout = Layout(
            grid_template_columns = "auto auto auto",
            grid_gap = "20px 40px",
            align_content = "flex-start"
        )
        ui_grid = GridBox([
            self._create_vbox("Canvas", (self._clear_button, self._random_button)),
            self._create_vbox("Options", (self._animation_checkbox, self._random_number_hbox)),
            self._create_vbox("", (self._animation_speed_hbox, self._random_message), right_aligned = True),
            self._create_vbox("Examples", self._example_buttons),
            self._create_vbox("Algorithms", self._algorithm_buttons),
            self._create_vbox("Messages", self._algorithm_messages, right_aligned = True)
        ], layout = ui_grid_layout)

        display(HBox(
            [VBox([self._canvas_output, self._instance_size_info]), ui_grid],
            layout = Layout(justify_content = "space-around")
        ))

    def add_point(self, point: Point) -> bool:
        if self._number_of_points >= self._MAX_NUMBER_OF_POINTS or not self._is_point_in_range(point):
            return False

        was_point_added = self._instance.add_point(point)
        if was_point_added:
            self._instance_drawer.draw((point,))
            self._number_of_points += 1
            self._update_instance_size_info()

        return was_point_added

    def add_points(self, points: list[Point]):
        added_points: list[Point] = []

        for point in points:
            if self._number_of_points >= self._MAX_NUMBER_OF_POINTS or not self._is_point_in_range(point):
                break
            if self._instance.add_point(point):
                added_points.append(point)
                self._number_of_points += 1

        self._instance_drawer.draw(added_points)
        self._update_instance_size_info()

    def clear(self):
        self.clear_instance()
        self.clear_algorithm_drawings()
        self.clear_algorithm_messages()

    def clear_instance(self):
        self._instance.clear()
        self._instance_drawer.clear()
        self._number_of_points = 0
        self._update_instance_size_info()

    def clear_algorithm_drawings(self):
        if self._current_algorithm_drawer is not None:
            self._current_algorithm_drawer.clear()

    def clear_algorithm_messages(self):
        for message in self._algorithm_messages:
            message.value = "<br>"

    def register_example_instance(self, name: str, instance: I):
        example_instance_points = self._instance.extract_points_from_raw_instance(instance)
        if len(example_instance_points) > self._MAX_NUMBER_OF_POINTS:
            raise ValueError(f"Can't register instance with more than {self._MAX_NUMBER_OF_POINTS} points.")
        for point in example_instance_points:
            if not self._is_point_in_range(point):
                raise ValueError(f"Can't register instance because the contained point {point} is out of range.")

        def example_instance_callback():
            self.clear()
            self.add_points(example_instance_points)

        self._example_buttons.append(self._create_button(name, example_instance_callback))

    def register_algorithm(self, name: str, algorithm: Algorithm[I], drawing_mode: DrawingMode):
        algorithm_drawer = Drawer(drawing_mode, self._ab_canvas, self._am_canvas, self._af_canvas)
        index = len(self._algorithm_messages)
        self._algorithm_messages.append(HTML("<br>"))

        def algorithm_callback():
            self.clear_algorithm_drawings()
            self._algorithm_messages[index].value = "<b>RUNNING</b>"

            try:
                algorithm_output, algorithm_running_time = self._instance.run_algorithm(algorithm)
            except BaseException as exception:
                title = html.escape(str(exception), quote = True)
                self._algorithm_messages[index].value = f"<b title='{title}'><font color='red'>ERROR</font></b>"
                return

            if not self._animation_checkbox.value:
                algorithm_drawer.draw(algorithm_output.points())
            else:
                self._algorithm_messages[index].value = "<b><font color='blue'>ANIMATING</font></b>"
                animation_time_step = 0.8 ** self._animation_speed_int_text.value
                algorithm_drawer.animate(algorithm_output.animation_events(), animation_time_step)

            self._algorithm_messages[index].value = f"{algorithm_running_time:.3f} ms"
            self._current_algorithm_drawer = algorithm_drawer

        self._algorithm_buttons.append(self._create_button(name, algorithm_callback))

    def disable_widgets(self):
        for widget in self._activatable_widgets():
            widget.disabled = True

    def enable_widgets(self):
        for widget in self._activatable_widgets():
            widget.disabled = False


    ## Helper methods.

    def _create_button(self, description: str, callback: Callable, layout: Optional[Layout] = None) -> Button:
        if layout is None:
            layout = Layout(width = self._DEFAULT_ITEM_WIDTH)
        style = ButtonStyle(button_color = "rgb(229, 228, 226)", font_weight = "600")

        def button_callback(_: Button):
            self.disable_widgets()
            callback()
            self.enable_widgets()
            self._previous_callback_finish_time = time.time()

        button = Button(description = description, layout = layout, style = style)
        button.on_click(button_callback)

        return button

    @staticmethod
    def _create_vbox(header: Optional[str], widgets: Iterable[Widget], right_aligned: bool = False) -> VBox:
        layout = Layout(grid_gap = "10px", align_items = "flex-end" if right_aligned else "flex-start")
        vbox = VBox(widgets, layout = layout)

        if header is None:
            return vbox
        elif header.strip() == "":
            header = "<br>"
        else:
            header = html.escape(header, quote = True)

        return VBox([HTML(f"<h2>{header}</h2>"), vbox])

    def _is_point_in_range(self, point: Point) -> bool:
        return 0 <= point.x <= self._width and 0 <= point.y <= self._height

    def _update_instance_size_info(self):
        info_value = f"Instance size: {self._instance.size():0>3}"
        if self._number_of_points != self._instance.size():
            info_value += f" (Number of points: {self._number_of_points:0>3})"
        self._instance_size_info.value = info_value

    def _activatable_widgets(self) -> Iterable[Widget]:
        return (
            self._clear_button,
            self._random_button, self._random_number_int_text,
            self._animation_checkbox, self._animation_speed_int_text,
            *self._example_buttons, *self._algorithm_buttons
        )
