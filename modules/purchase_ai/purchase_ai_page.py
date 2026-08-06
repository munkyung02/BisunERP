"""Sprint 5.1.3 AI 발주센터 · 공급처 조건 최적화 화면."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .purchase_ai_service import PurchaseAIService


class PurchaseAIPage(ttk.Frame):
    def __init__(self, parent: tk.Widget, *, status_callback: Callable[[str], None] | None = None,
                 service: PurchaseAIService | None = None) -> None:
        super().__init__(parent, padding=18)
        self.status_callback = status_callback or (lambda _message: None)
        self.service = service or PurchaseAIService()
        self.kpi_vars = {key: tk.StringVar(value="0") for key in ("plans", "suppliers", "urgent", "amount", "savings")}
        self.pending_var = tk.StringVar(value="추천 대기 상품 0건")
        self.reason_var = tk.StringVar(value="발주계획을 선택하면 추천 사유가 표시됩니다.")
        self.preview_title_var = tk.StringVar(value="공급처별 발주서 Preview")
        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="AI 발주센터", font=("맑은 고딕", 22, "bold")).pack(side="left")
        ttk.Label(top, text="Sprint 5.1.3 · 단가·MOQ·포장단위·배송비 최적화", font=("맑은 고딕", 10)).pack(side="left", padx=12, pady=(8, 0))
        ttk.Button(top, text="새로고침", command=self.refresh_data).pack(side="right")
        ttk.Button(top, text="배송상세 복사", command=lambda: self.copy_purchase_text(True)).pack(side="right", padx=6)
        ttk.Button(top, text="발주내용 복사", command=lambda: self.copy_purchase_text(False)).pack(side="right", padx=6)
        ttk.Button(top, text="발주서 엑셀", command=self.export_purchase_excel).pack(side="right", padx=6)
        ttk.Button(top, text="발주 확정", command=self.confirm_selected_plan).pack(side="right", padx=6)
        ttk.Button(top, text="추천 다시 계산", command=self.recalculate).pack(side="right", padx=6)
        ttk.Button(top, text="공급처별 계획 생성", command=self.generate_groups).pack(side="right", padx=6)
        ttk.Label(top, textvariable=self.pending_var).pack(side="right", padx=12)

        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill="x", pady=(16, 14))
        for index, (title, key) in enumerate([
            ("오늘 발주계획", "plans"), ("공급처 수", "suppliers"),
            ("긴급발주", "urgent"), ("예상금액", "amount"), ("예상 절감", "savings"),
        ]):
            card = ttk.LabelFrame(kpi_frame, text=title, padding=12)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0))
            kpi_frame.columnconfigure(index, weight=1)
            ttk.Label(card, textvariable=self.kpi_vars[key], font=("맑은 고딕", 18, "bold")).pack()

        plan_box = ttk.LabelFrame(self, text="추천 발주 목록", padding=8)
        plan_box.pack(fill="x")
        self.plan_tree = ttk.Treeview(
            plan_box,
            columns=("priority", "supplier", "score", "orders", "items", "qty", "amount", "shipping", "saving", "deadline", "status", "reason"),
            show="headings", height=8,
        )
        specs = [
            ("priority", "우선", 58, "center"), ("supplier", "공급처", 130, "w"),
            ("score", "성적", 58, "center"), ("orders", "주문", 55, "center"),
            ("items", "상품", 55, "center"), ("qty", "수량", 55, "center"),
            ("amount", "예상금액", 95, "e"), ("shipping", "배송비", 75, "e"),
            ("saving", "절감", 75, "e"), ("deadline", "마감", 62, "center"),
            ("status", "상태", 75, "center"), ("reason", "추천 사유", 300, "w"),
        ]
        for key, text, width, anchor in specs:
            self.plan_tree.heading(key, text=text)
            self.plan_tree.column(key, width=width, anchor=anchor, stretch=key in ("supplier", "reason"))
        self.plan_tree.pack(fill="x")
        self.plan_tree.bind("<<TreeviewSelect>>", self._load_selected_plan)
        self.plan_tree.tag_configure("urgent", background="#ffe6e6")
        self.plan_tree.tag_configure("confirmed", foreground="#777777")

        reason_frame = ttk.Frame(self)
        reason_frame.pack(fill="x", pady=(8, 10))
        ttk.Label(reason_frame, text="추천 사유", font=("맑은 고딕", 10, "bold")).pack(side="left")
        ttk.Label(reason_frame, textvariable=self.reason_var).pack(side="left", padx=10)

        middle = ttk.Panedwindow(self, orient="horizontal")
        middle.pack(fill="both", expand=True)
        detail_box = ttk.LabelFrame(middle, text="원주문 상품 · 발주 제외 관리", padding=8)
        preview_box = ttk.LabelFrame(middle, text=self.preview_title_var.get(), padding=8)
        middle.add(detail_box, weight=3)
        middle.add(preview_box, weight=2)

        detail_tools = ttk.Frame(detail_box)
        detail_tools.pack(fill="x", pady=(0, 6))
        ttk.Button(detail_tools, text="이번 발주 제외", command=lambda: self.toggle_excluded(True)).pack(side="left")
        ttk.Button(detail_tools, text="제외 취소", command=lambda: self.toggle_excluded(False)).pack(side="left", padx=6)
        ttk.Label(detail_tools, text="같은 상품·옵션은 오른쪽 Preview에서 자동 합산됩니다.").pack(side="right")

        self.detail_tree = ttk.Treeview(
            detail_box,
            columns=("excluded", "order", "product", "option", "ordered", "purchase", "waste", "price", "amount"),
            show="headings", height=12, selectmode="extended",
        )
        for key, text, width, anchor in [
            ("excluded", "제외", 48, "center"), ("order", "주문번호", 105, "w"),
            ("product", "상품", 155, "w"), ("option", "옵션", 90, "w"),
            ("ordered", "주문", 48, "center"), ("purchase", "발주", 48, "center"),
            ("waste", "추가", 48, "center"), ("price", "매입가", 70, "e"),
            ("amount", "금액", 78, "e"),
        ]:
            self.detail_tree.heading(key, text=text)
            self.detail_tree.column(key, width=width, anchor=anchor, stretch=key == "product")
        self.detail_tree.pack(fill="both", expand=True)
        self.detail_tree.tag_configure("excluded", foreground="#999999")
        self.detail_tree.tag_configure("confirmed", foreground="#356b35")

        self.preview_tree = ttk.Treeview(
            preview_box,
            columns=("product", "option", "orders", "ordered", "qty", "waste", "price", "amount"),
            show="headings", height=12,
        )
        for key, text, width, anchor in [
            ("product", "상품", 145, "w"), ("option", "옵션", 80, "w"),
            ("orders", "주문", 48, "center"), ("ordered", "주문수량", 62, "center"),
            ("qty", "발주수량", 62, "center"), ("waste", "추가", 48, "center"),
            ("price", "단가", 68, "e"), ("amount", "금액", 82, "e"),
        ]:
            self.preview_tree.heading(key, text=text)
            self.preview_tree.column(key, width=width, anchor=anchor, stretch=key == "product")
        self.preview_tree.pack(fill="both", expand=True)

        recent_box = ttk.LabelFrame(self, text="최근 생성된 발주계획", padding=8)
        recent_box.pack(fill="x", pady=(12, 0))
        self.recent_tree = ttk.Treeview(
            recent_box, columns=("created", "supplier", "orders", "qty", "amount", "status"),
            show="headings", height=4,
        )
        for key, text, width in [
            ("created", "생성일시", 140), ("supplier", "공급처", 170), ("orders", "주문", 65),
            ("qty", "수량", 65), ("amount", "예상금액", 105), ("status", "상태", 80),
        ]:
            self.recent_tree.heading(key, text=text)
            self.recent_tree.column(key, width=width, anchor="w" if key == "supplier" else "center")
        self.recent_tree.pack(fill="x")

    @staticmethod
    def _priority_label(priority: int) -> str:
        return {1: "★★★★★", 2: "★★★★☆", 3: "★★★☆☆"}.get(int(priority or 3), "★★★☆☆")

    def _selected_plan_id(self) -> int | None:
        selected = self.plan_tree.selection()
        return int(selected[0]) if selected else None

    def copy_purchase_text(self, include_delivery: bool = False) -> None:
        plan_id = self._selected_plan_id()
        if plan_id is None:
            messagebox.showwarning("선택 필요", "복사할 발주계획을 선택해 주세요.")
            return
        try:
            text = self.service.build_purchase_message(plan_id, include_delivery=include_delivery)
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
            label = "배송상세 포함 발주내용" if include_delivery else "발주요약"
            self.status_callback(f"{label}을 클립보드에 복사했습니다.")
            messagebox.showinfo("복사 완료", f"{label}을 복사했습니다. 카카오톡이나 문자에 붙여넣으세요.")
        except Exception as exc:
            messagebox.showerror("복사 실패", str(exc))

    def export_purchase_excel(self) -> None:
        plan_id = self._selected_plan_id()
        if plan_id is None:
            messagebox.showwarning("선택 필요", "저장할 발주계획을 선택해 주세요.")
            return
        preview = self.service.get_plan_preview(plan_id)
        supplier = str(preview["plan"].get("supplier_name", "공급처")).replace("/", "_").replace("\\", "_")
        filename = f"{supplier}_발주서.xlsx"
        path = filedialog.asksaveasfilename(
            title="발주서 엑셀 저장", defaultextension=".xlsx", initialfile=filename,
            filetypes=[("Excel 파일", "*.xlsx")],
        )
        if not path:
            return
        try:
            saved = self.service.export_purchase_excel(plan_id, path)
            self.status_callback(f"발주서 저장 완료: {saved}")
            messagebox.showinfo("저장 완료", f"발주서 엑셀을 저장했습니다.\n\n{saved}")
        except Exception as exc:
            messagebox.showerror("저장 실패", str(exc))

    def generate_groups(self) -> None:
        try:
            result = self.service.generate_supplier_groups()
            self.refresh_data()
            message = (
                f"공급처 {result['supplier_count']:,}곳 / 주문상품 {result['item_count']:,}건을 "
                f"발주계획 {result['plan_count']:,}건으로 추천했습니다.\n"
                f"긴급 발주: {result['urgent_count']:,}건\n"
                f"예상 매입금액: {result['estimated_amount']:,}원\n"
                f"조건 없음 제외: {result['excluded_count']:,}건\n"
                f"차선 공급처 대비 예상 절감: {result.get('savings_amount', 0):,}원"
            )
            messagebox.showinfo("AI 발주 추천 생성 완료", message)
            self.status_callback(message.replace("\n", " · "))
        except Exception as exc:
            messagebox.showerror("추천 생성 실패", str(exc))
            self.status_callback(f"AI 발주 추천 생성 실패: {exc}")

    def recalculate(self) -> None:
        try:
            result = self.service.recalculate_recommendations()
            self.refresh_data()
            message = f"발주계획 {result['plan_count']:,}건의 추천을 다시 계산했습니다. 긴급 {result['urgent_count']:,}건"
            self.status_callback(message)
            messagebox.showinfo("추천 재계산 완료", message)
        except Exception as exc:
            messagebox.showerror("추천 재계산 실패", str(exc))

    def toggle_excluded(self, excluded: bool) -> None:
        plan_id = self._selected_plan_id()
        selected = self.detail_tree.selection()
        if plan_id is None or not selected:
            messagebox.showwarning("선택 필요", "발주계획과 원주문 상품을 선택해 주세요.")
            return
        try:
            for iid in selected:
                self.service.set_item_excluded(int(iid), excluded)
            self.refresh_data(select_plan_id=plan_id)
            self.status_callback(f"선택 상품 {len(selected):,}건 {'발주 제외' if excluded else '제외 취소'} 완료")
        except Exception as exc:
            messagebox.showerror("처리 실패", str(exc))

    def confirm_selected_plan(self) -> None:
        plan_id = self._selected_plan_id()
        if plan_id is None:
            messagebox.showwarning("선택 필요", "확정할 발주계획을 선택해 주세요.")
            return
        preview = self.service.get_plan_preview(plan_id)
        plan = preview["plan"]
        if not messagebox.askyesno(
            "발주 확정",
            f"{plan['supplier_name']} 발주계획을 확정하시겠습니까?\n\n"
            f"상품 {len(preview['items']):,}종 · 수량 {int(plan['total_quantity'] or 0):,}\n"
            f"예상금액 {int(plan['estimated_amount'] or 0):,}원\n\n"
            "확정하면 제외되지 않은 주문상품이 기존 발주관리로 전달됩니다.",
        ):
            return
        try:
            result = self.service.confirm_plan(plan_id)
            self.refresh_data(select_plan_id=plan_id)
            message = (f"발주계획을 확정했습니다. 주문 {result['order_count']:,}건 / "
                       f"상품 {result['item_count']:,}건 / 신규 발주등록 {result['inserted_count']:,}건")
            messagebox.showinfo("발주 확정 완료", message)
            self.status_callback(message)
        except Exception as exc:
            messagebox.showerror("발주 확정 실패", str(exc))

    def refresh_data(self, select_plan_id: int | None = None) -> None:
        try:
            data = self.service.get_dashboard_data()
        except Exception as exc:
            messagebox.showerror("AI 발주센터 조회 실패", str(exc))
            return
        kpi = data["kpi"]
        self.kpi_vars["plans"].set(f"{int(kpi.get('plan_count', 0) or 0):,}건")
        self.kpi_vars["suppliers"].set(f"{int(kpi.get('supplier_count', 0) or 0):,}곳")
        self.kpi_vars["urgent"].set(f"{int(kpi.get('urgent_count', 0) or 0):,}건")
        self.kpi_vars["amount"].set(f"{int(kpi.get('estimated_amount', 0) or 0):,}원")
        self.kpi_vars["savings"].set(f"{int(kpi.get('savings_amount', 0) or 0):,}원")
        self.pending_var.set(f"추천 대기 상품 {int(data.get('pending_item_count', 0)):,}건")
        self._clear(self.plan_tree)
        self._clear(self.detail_tree)
        self._clear(self.preview_tree)
        for row in data["plans"]:
            priority = int(row.get("priority", 3) or 3)
            tags = ("confirmed",) if int(row.get("confirmed", 0) or 0) else (("urgent",) if priority == 1 else ())
            self.plan_tree.insert(
                "", "end", iid=str(row["id"]), tags=tags,
                values=(self._priority_label(priority), row["supplier_name"], f"{float(row['supplier_score'] or 0):.0f}",
                        row["order_count"], row["item_count"], row["total_quantity"],
                        f"{int(row['estimated_amount'] or 0):,}", f"{int(row.get('shipping_fee', 0) or 0):,}",
                        f"{int(row.get('savings_amount', 0) or 0):,}", row["deadline_time"], row["status"],
                        row.get("recommended_reason", "")),
            )
        self._clear(self.recent_tree)
        for row in data["recent"]:
            self.recent_tree.insert("", "end", values=(
                row["created_at"], row["supplier_name"], row["order_count"], row["total_quantity"],
                f"{int(row['estimated_amount'] or 0):,}", row["status"],
            ))
        if select_plan_id is not None and self.plan_tree.exists(str(select_plan_id)):
            self.plan_tree.selection_set(str(select_plan_id))
            self.plan_tree.focus(str(select_plan_id))
            self._load_selected_plan()
        else:
            self.reason_var.set("발주계획을 선택하면 추천 사유가 표시됩니다.")
            self.preview_title_var.set("공급처별 발주서 Preview")
        self.status_callback("AI 발주 추천센터 새로고침 완료")

    def _load_selected_plan(self, _event=None) -> None:
        plan_id = self._selected_plan_id()
        self._clear(self.detail_tree)
        self._clear(self.preview_tree)
        if plan_id is None:
            return
        try:
            preview = self.service.get_plan_preview(plan_id)
            plan = preview["plan"]
            self.reason_var.set(str(plan.get("recommended_reason", "")) or "추천 사유 없음")
            self.preview_title_var.set(
                f"{plan['supplier_name']} 발주서 Preview · 성적 {float(plan.get('supplier_score', 0) or 0):.0f}점"
            )
            for row in self.service.get_plan_items(plan_id):
                tags = ("confirmed",) if int(row.get("confirmed", 0) or 0) else (("excluded",) if int(row.get("excluded", 0) or 0) else ())
                self.detail_tree.insert(
                    "", "end", iid=str(row["id"]), tags=tags,
                    values=("제외" if int(row.get("excluded", 0) or 0) else "", row["order_number"],
                            row["product_name"], row["option_name"], row.get("ordered_quantity", row["quantity"]),
                            row.get("purchase_quantity", row["quantity"]), row.get("waste_quantity", 0),
                            f"{int(row['purchase_price'] or 0):,}", f"{int(row['estimated_amount'] or 0):,}"),
                )
            for row in preview["items"]:
                self.preview_tree.insert("", "end", values=(
                    row["product_name"], row["option_name"], row["order_count"], row.get("ordered_quantity", row["quantity"]),
                    row["quantity"], row.get("waste_quantity", 0), f"{int(row['purchase_price'] or 0):,}",
                    f"{int(row['estimated_amount'] or 0):,}",
                ))
        except Exception as exc:
            messagebox.showerror("발주계획 조회 실패", str(exc))

    @staticmethod
    def _clear(tree: ttk.Treeview) -> None:
        for item in tree.get_children():
            tree.delete(item)
