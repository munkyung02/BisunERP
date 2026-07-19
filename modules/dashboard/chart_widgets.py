from __future__ import annotations

import tkinter as tk
from typing import Any


class SevenDayChart(tk.Canvas):
    """외부 패키지 없이 최근 7일 주문/매출을 그리는 Tkinter 차트입니다."""

    def __init__(self, parent: tk.Misc, **kwargs: Any) -> None:
        kwargs.setdefault("height", 230)
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("background", "white")
        super().__init__(parent, **kwargs)
        self._rows: list[dict[str, Any]] = []
        self._metric = "order_count"
        self.bind("<Configure>", lambda _event: self._draw())

    def set_data(self, rows: list[dict[str, Any]], metric: str) -> None:
        self._rows = rows[-7:]
        self._metric = metric
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 400)
        height = max(self.winfo_height(), 210)
        left, top, right, bottom = 54, 24, width - 18, height - 42

        self.create_line(left, top, left, bottom, fill="#b8bec6")
        self.create_line(left, bottom, right, bottom, fill="#b8bec6")

        if not self._rows:
            self.create_text(
                width / 2,
                height / 2,
                text="표시할 데이터가 없습니다.",
                fill="#707780",
                font=("맑은 고딕", 11),
            )
            return

        values = [max(0, self._to_int(row.get(self._metric))) for row in self._rows]
        maximum = max(values) or 1
        plot_width = max(1, right - left)
        plot_height = max(1, bottom - top)
        slot = plot_width / max(1, len(values))
        bar_width = min(54, slot * 0.55)

        for guide in range(5):
            y = bottom - (plot_height * guide / 4)
            value = int(maximum * guide / 4)
            self.create_line(left, y, right, y, fill="#edf0f3")
            label = self._format_value(value)
            self.create_text(
                left - 8,
                y,
                text=label,
                anchor="e",
                fill="#707780",
                font=("맑은 고딕", 8),
            )

        for index, (row, value) in enumerate(zip(self._rows, values)):
            center_x = left + slot * index + slot / 2
            bar_height = plot_height * value / maximum
            y1 = bottom - bar_height
            self.create_rectangle(
                center_x - bar_width / 2,
                y1,
                center_x + bar_width / 2,
                bottom,
                fill="#3264a8",
                outline="",
            )
            self.create_text(
                center_x,
                y1 - 10,
                text=self._format_value(value),
                fill="#28323c",
                font=("맑은 고딕", 8, "bold"),
            )
            self.create_text(
                center_x,
                bottom + 16,
                text=str(row.get("label") or "-"),
                fill="#555e68",
                font=("맑은 고딕", 8),
            )

    def _format_value(self, value: int) -> str:
        if self._metric == "sales":
            if value >= 100_000_000:
                return f"{value / 100_000_000:.1f}억"
            if value >= 10_000:
                return f"{value / 10_000:.0f}만"
            return f"{value:,}"
        return f"{value:,}"

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return 0
