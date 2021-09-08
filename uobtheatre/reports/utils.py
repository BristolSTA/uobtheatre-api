import io
from datetime import datetime
from typing import List, Tuple

import xlsxwriter
from django.http.response import HttpResponse

from uobtheatre.users.models import User

from . import reports


class ExcelReport:  # pragma: no cover
    """Generates an Excel xlxs spreadsheet"""

    def __init__(
        self,
        name: str = None,
        descriptions: List = None,
        meta: List = None,
        user: User = None,
    ) -> None:
        self.name = name
        self.output_buffer = io.BytesIO()
        self.row_tracker = 1  # Track the row we are currently at

        # Setup Workbook and Sheet
        self.workbook = xlsxwriter.Workbook(self.output_buffer)
        self.worksheet = self.workbook.add_worksheet()

        # Setup Formatters
        self.formats = {
            "bold": self.workbook.add_format({"bold": True}),
            "dataset_title": self.workbook.add_format(
                {"underline": True, "bold": True}
            ),
            "currency": self.workbook.add_format({"num_format": "£#,##0.00"}),
        }

        if not meta:
            meta = []

        # Add default meta
        meta.append(["Generated At", datetime.now().strftime("%Y-%m-%d %H:%M")])
        if user:
            meta.append(["Generated By", str(user)])

        # Add Header
        self.write_bold("A1", "UOB Theatre")
        self.worksheet.set_column("A:A", 15)
        self.worksheet.set_column("B:B", 20)
        if name:
            self.write("B1", name)

        self.increment_row_tracker(amount=2)

        # Add meta
        if len(meta) > 0:
            for i, item in enumerate(meta):
                if isinstance(item, List):
                    self.write_bold("A%s" % self.row_tracker, item[0])
                    self.write("B%s" % self.row_tracker, item[1])
                self.increment_row_tracker()

        # Add description
        if descriptions and len(descriptions) > 0:
            self.worksheet.set_column("D:D", 20)
            self.write_bold("D1", "Description and Usage Notes:")
            for i, item in enumerate(descriptions):
                row_num = 2 + i
                self.write("D%s" % row_num, item)
                self.increment_row_tracker(current_row=row_num)

        self.increment_row_tracker(amount=2)  # Add gap

    def increment_row_tracker(self, current_row=None, amount=1) -> None:
        """Increments the row tracker"""
        if current_row:
            if current_row >= self.row_tracker:
                self.row_tracker = current_row
            else:
                return
        self.row_tracker += amount

    def write_formula(self, *args) -> None:
        self.worksheet.write_formula(*args)

    def write_bold(self, row, col, *args) -> None:
        """Writes bold text to the given cell

        Args:
            row (str|int): Either the rowcol location (e.g. "A1") or row number
            col (str|int): Either the text to write, or the column number
        """
        self.write(row, col, *args, self.formats["bold"])

    def write_currency(self, row, col, *args) -> None:
        """Writes currency text to the given cell

        Args:
            row (str|int): Either the rowcol location (e.g. "A1") or row number
            col (str|int): Either the text to write, or the column number
        """
        self.write(row, col, *args, self.formats["currency"])

    def write_list(
        self,
        start: Tuple[int, int],
        items: List,
        title: str = None,
        items_format: str = None,
    ):
        """Writes a list (with optional header)"""
        start_row = start[0]
        if title:
            self.write_bold(start_row, start[1], title)
            start_row += 1

        for i, item in enumerate(items):
            self.write(
                start_row + i,
                start[1],
                item,
                self.formats[items_format] if items_format else None,
            )
            self.increment_row_tracker(
                current_row=(start_row + i)
            )  # Plus one due to excel non-zero first row

    def write_dataset(self, dataset: reports.DataSet, start: Tuple[int, int]):
        self.write(start[0], start[1], dataset.name, self.formats["dataset_title"])
        for i, header in enumerate(dataset.headings):
            self.write_list(
                (start[0] + 1, start[1] + i), [data[i] for data in dataset.data], header
            )

    def write(self, *args, **kwargs) -> None:
        """Write to the spreadsheet"""
        self.worksheet.write(*args, **kwargs)

    def set_col_width(self, *args):
        self.worksheet.set_column(*args)

    def datasets_to_response(self, datasets):
        """Converts a list of datasets into a standard XLSX file and returns a Http response to download the result"""
        for dataset in datasets:
            self.write_dataset(dataset, (self.row_tracker, 0))
            self.increment_row_tracker()

        response = HttpResponse(
            self.get_output(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            "attachment; filename=%s" % self.name.lower().replace(" ", "_") + ".xlsx"
        )
        return response

    def get_output(self) -> io.BytesIO:
        """Gets the output buffer, starting at the start"""
        self.workbook.close()

        self.output_buffer.seek(0)
        return self.output_buffer
