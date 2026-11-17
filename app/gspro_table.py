"""A table on a GSPro screen: a list of rows, each with buttons in fixed columns. The course list is one.

A table is a plugin piece. It knows where its rows and columns are on the window (fractions of the window, as the
rest of the app uses), which row word names each row ("one" to "nine"), what each row shows as last read (play,
download, or empty), and where the overlay boxes for its columns go. It knows nothing about courses: the game's
module says what the columns do.
"""

from dataclasses import dataclass, field

from app.connector_ui import _point
from app.gspro_pixels import classify_button, pixel_colour


@dataclass(frozen=True)
class Column:
    """One column of buttons. click_x is where a click lands. box_x and box_width are the overlay box for it."""

    click_x: float
    box_x: float
    box_width: float


@dataclass
class Table:
    name: str
    digits: tuple[str, ...]  # every digit word in order: the index is the digit (zero is 0)
    rows: tuple[str, ...]  # the digit words of the rows this table has, top to bottom
    first_row_y: float  # the centre of row one, as a fraction of the window height
    row_step: float  # the distance between rows
    edge_x: float  # where the button colour is read: the label in the middle is white and reads as neither
    columns: dict[str, Column]
    row_box_dy: float = 0.0  # the row boxes sit this far below the row centre (overlay only; clicks are not moved)
    row_half_height: float = 0.02  # half the height of a row box
    states: dict[int, str | None] = field(default_factory=dict)  # row number -> "play", "download" or None, as last read

    def number(self, word: str) -> int:
        """The row number of a digit word: its digit ("one" is 1, "five" is 5)."""
        return self.digits.index(word)

    def row_numbers(self) -> list[int]:
        """The row numbers this table has, top to bottom."""
        return [self.number(word) for word in self.rows]

    def row_y(self, number: int) -> float:
        """The centre of a row, as a fraction of the window height. The first row of the table is at first_row_y."""
        return self.first_row_y + (number - self.number(self.rows[0])) * self.row_step

    def point(self, number: int, column: str) -> tuple[float, float]:
        """Where a click on this row's column lands, as fractions of the window."""
        return self.columns[column].click_x, self.row_y(number)

    def edge_point(self, number: int) -> tuple[float, float]:
        """Where the row's button colour is read, as fractions of the window."""
        return self.edge_x, self.row_y(number)

    def box(self, column: str, word: str) -> tuple[tuple[float, float], tuple[float, float, float, float]]:
        """(centre, (left, top, width, height)) of the overlay box for this row's column, as fractions of the window."""
        col = self.columns[column]
        centre_y = self.row_y(self.number(word)) + self.row_box_dy
        return (col.box_x, centre_y), (
            col.box_x - col.box_width / 2, centre_y - self.row_half_height, col.box_width, 2 * self.row_half_height,
        )

    def read_states(self, rect) -> None:
        """Reads each row's button from the screen: blue is play, grey is download, anything else is an empty row."""
        for number in self.row_numbers():
            x, y = _point(rect, self.edge_point(number))
            self.states[number] = classify_button(*pixel_colour(x, y))

    def state(self, number: int) -> str | None:
        """"play", "download" or None for a row number, as last read."""
        return self.states.get(number)
