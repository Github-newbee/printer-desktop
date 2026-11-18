from __future__ import annotations

import re
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from app_core import DesktopRuntime
from services.errors import ServiceError
from services.print_options import DEFAULT_PAPER_SIZE, get_paper_size_options


PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?:\s|/|>)")
STATUS_LABELS = {
    "pending": "待打印",
    "printing": "打印中",
    "submitted": "已提交",
    "success": "已完成",
    "failed": "打印失败",
    "deleted": "已清理",
}


@dataclass
class BatchItem:
    key: str
    path: Path
    pages: int
    page_range: str
    copies: int = 1
    selected: bool = True
    status: str = "待打印"
    job_id: str = ""


def count_pdf_pages(path: Path) -> int:
    count = 0
    carry = b""
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            data = carry + chunk
            carry_length = len(carry)
            count += sum(1 for match in PAGE_PATTERN.finditer(data) if match.end() > carry_length)
            carry = data[-32:]
    return max(count, 1)


def pages_in_range(page_range: str, total_pages: int) -> int:
    value = page_range.replace(" ", "").strip()
    if not value:
        return total_pages
    total = 0
    try:
        for part in value.split(","):
            if not part:
                continue
            if "-" in part:
                start, end = (int(number) for number in part.split("-", 1))
                total += max(end - start + 1, 0)
            else:
                total += 1
    except ValueError:
        return total_pages
    return min(total, total_pages)


class DesktopApp:
    def __init__(self, root: tk.Tk, runtime: DesktopRuntime) -> None:
        self.root = root
        self.runtime = runtime
        self.items: list[BatchItem] = []
        self.paper_sizes = {item["code"]: item for item in get_paper_size_options()}
        self.paper_size = DEFAULT_PAPER_SIZE
        self.orientation = "landscape"
        self.events: Queue[tuple[str, object]] = Queue()
        self.edit_entry: tk.Entry | None = None
        self.edit_item: str | None = None
        self.edit_column: str | None = None
        self._build_window()
        self._load_printers()
        self._refresh_history()
        self.root.after(100, self._poll_events)
        self.root.after(5000, self._auto_refresh)

    def _build_window(self) -> None:
        self.root.title("批量打印")
        self.root.geometry("1120x720")
        self.root.minsize(900, 600)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="批量打印", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(header, text="PDF 进入队列后由本机打印服务依次提交", foreground="#666").pack(side="left", padx=(14, 0), pady=(8, 0))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="用户名称").pack(side="left")
        self.user_name = ttk.Entry(controls, width=18)
        self.user_name.pack(side="left", padx=(6, 18))
        ttk.Label(controls, text="打印机").pack(side="left")
        self.printer_combo = ttk.Combobox(controls, state="readonly", width=38)
        self.printer_combo.pack(side="left", padx=6)
        ttk.Button(controls, text="刷新打印机", command=self._load_printers).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="打印设置", command=self._open_settings).pack(side="right")

        table_frame = ttk.Frame(outer)
        table_frame.pack(fill="both", expand=True)
        columns = ("select", "name", "pages", "range", "copies", "status", "job")
        self.file_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {"select": "选择", "name": "文件名", "pages": "页数", "range": "打印范围", "copies": "份数", "status": "状态", "job": "任务 ID"}
        widths = {"select": 55, "name": 300, "pages": 70, "range": 140, "copies": 70, "status": 100, "job": 190}
        for column in columns:
            self.file_tree.heading(column, text=headings[column])
            self.file_tree.column(column, width=widths[column], anchor="center" if column != "name" else "w")
        self.file_tree.tag_configure("error", foreground="#b42318")
        self.file_tree.tag_configure("done", foreground="#087443")
        self.file_tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.file_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        self.file_tree.bind("<Button-1>", self._on_tree_click)
        self.file_tree.bind("<Double-1>", self._on_tree_double_click)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(12, 4))
        ttk.Button(actions, text="添加文件", command=self._add_files).pack(side="left")
        ttk.Button(actions, text="添加文件夹", command=self._add_folder).pack(side="left", padx=6)
        ttk.Button(actions, text="清除选中", command=self._clear_selected).pack(side="left")
        self.summary = ttk.Label(actions, text="总计：0 个文件，共 0 页，耗纸 0 张")
        self.summary.pack(side="left", padx=18)
        self.start_button = ttk.Button(actions, text="开始打印", command=self._start_batch)
        self.start_button.pack(side="right")
        self.message = ttk.Label(outer, text="", foreground="#087443")
        self.message.pack(fill="x", pady=(4, 12))

        ttk.Label(outer, text="最近任务", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(4, 8))
        self.history = ttk.Treeview(outer, columns=("file", "printer", "status", "time"), show="headings", height=7)
        for column, heading, width in (("file", "文件名", 360), ("printer", "打印机", 300), ("status", "状态", 120), ("time", "创建时间", 220)):
            self.history.heading(column, text=heading)
            self.history.column(column, width=width, anchor="w")
        self.history.pack(fill="x")

    def _load_printers(self) -> None:
        try:
            printers = self.runtime.printer_service.list_printers()
        except RuntimeError as exc:
            self.printer_combo["values"] = ()
            self._show_message(str(exc), error=True)
            return
        names = [printer["name"] for printer in printers]
        current = self.printer_combo.get()
        self.printer_combo["values"] = names
        if current in names:
            self.printer_combo.set(current)
        elif names:
            self.printer_combo.current(0)
        else:
            self.printer_combo.set("")
            self._show_message("未找到可用打印机", error=True)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="选择 PDF 文件", filetypes=(("PDF 文件", "*.pdf"),))
        self._append_paths([Path(path) for path in paths])

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="选择 PDF 文件夹")
        if folder:
            self._append_paths(sorted(Path(folder).rglob("*.pdf")))

    def _append_paths(self, paths: list[Path]) -> None:
        existing = {item.path.resolve() for item in self.items}
        added = 0
        for path in paths:
            if path.suffix.lower() != ".pdf" or not path.is_file() or path.resolve() in existing:
                continue
            try:
                pages = count_pdf_pages(path)
            except OSError:
                continue
            self.items.append(BatchItem(str(len(self.items)), path, pages, f"1-{pages}"))
            existing.add(path.resolve())
            added += 1
        self._render_items()
        self._show_message(f"已添加 {added} 个 PDF 文件" if added else "没有可添加的 PDF 文件", error=not bool(added))

    def _render_items(self) -> None:
        for child in self.file_tree.get_children():
            self.file_tree.delete(child)
        for item in self.items:
            status = item.status
            tag = "error" if "失败" in status else "done" if status in {"已完成", "已提交"} else ""
            self.file_tree.insert("", "end", iid=item.key, values=("✓" if item.selected else "", item.path.name, item.pages, item.page_range, item.copies, status, item.job_id), tags=(tag,))
        selected = [item for item in self.items if item.selected]
        pages = sum(pages_in_range(item.page_range, item.pages) for item in selected)
        paper = sum(pages_in_range(item.page_range, item.pages) * item.copies for item in selected)
        self.summary["text"] = f"总计：{len(selected)} 个文件，共 {pages} 页，耗纸 {paper} 张"

    def _on_tree_click(self, event: tk.Event) -> None:
        row = self.file_tree.identify_row(event.y)
        column = self.file_tree.identify_column(event.x)
        if row and column == "#1":
            item = self._find_item(row)
            if item:
                item.selected = not item.selected
                self._render_items()

    def _on_tree_double_click(self, event: tk.Event) -> None:
        row = self.file_tree.identify_row(event.y)
        column = self.file_tree.identify_column(event.x)
        if not row or column not in {"#4", "#5"}:
            return
        bbox = self.file_tree.bbox(row, column)
        if not bbox:
            return
        item = self._find_item(row)
        if not item:
            return
        self._finish_edit()
        self.edit_item, self.edit_column = row, column
        self.edit_entry = tk.Entry(self.file_tree)
        value = item.page_range if column == "#4" else str(item.copies)
        self.edit_entry.insert(0, value)
        self.edit_entry.select_range(0, "end")
        self.edit_entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        self.edit_entry.focus_set()
        self.edit_entry.bind("<Return>", lambda _: self._finish_edit())
        self.edit_entry.bind("<FocusOut>", lambda _: self._finish_edit())

    def _finish_edit(self) -> None:
        if not self.edit_entry or not self.edit_item or not self.edit_column:
            return
        item = self._find_item(self.edit_item)
        value = self.edit_entry.get().strip()
        if item:
            if self.edit_column == "#4":
                item.page_range = value
            else:
                try:
                    item.copies = max(1, min(99, int(value or "1")))
                except ValueError:
                    self._show_message("打印份数必须是 1-99 的整数", error=True)
        self.edit_entry.destroy()
        self.edit_entry = self.edit_item = self.edit_column = None
        self._render_items()

    def _clear_selected(self) -> None:
        self.items = [item for item in self.items if not item.selected]
        self._render_items()

    def _open_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("打印设置")
        dialog.transient(self.root)
        dialog.grab_set()
        body = ttk.Frame(dialog, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="纸张大小").grid(row=0, column=0, sticky="w", pady=6)
        paper = ttk.Combobox(body, state="readonly", values=tuple(self.paper_sizes), width=24)
        paper.set(self.paper_size)
        paper.grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(body, text="纸张方向").grid(row=1, column=0, sticky="w", pady=6)
        orientation = tk.StringVar(value=self.orientation)
        ttk.Radiobutton(body, text="纵向", variable=orientation, value="portrait").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(body, text="横向", variable=orientation, value="landscape").grid(row=2, column=1, sticky="w")
        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="left", padx=4)
        def apply() -> None:
            self.paper_size = paper.get() or DEFAULT_PAPER_SIZE
            self.orientation = orientation.get()
            dialog.destroy()
            self._show_message(f"打印设置：{self.paper_size} · {'横向' if self.orientation == 'landscape' else '纵向'}")
        ttk.Button(buttons, text="应用", command=apply).pack(side="left", padx=4)
        body.columnconfigure(1, weight=1)

    def _start_batch(self) -> None:
        printer = self.printer_combo.get().strip()
        user_name = self.user_name.get().strip()
        selected = [item for item in self.items if item.selected]
        if not printer:
            self._show_message("请选择打印机", error=True)
            return
        if not selected:
            self._show_message("请选择要打印的文件", error=True)
            return
        self.start_button.configure(state="disabled")
        self._show_message("正在提交打印任务…")
        threading.Thread(target=self._submit_batch, args=(selected, printer, user_name), daemon=True).start()

    def _submit_batch(self, items: list[BatchItem], printer: str, user_name: str) -> None:
        success = 0
        for item in items:
            self.events.put(("status", (item.key, "提交中", "")))
            try:
                data = self.runtime.submit_file(item.path, printer, user_name, item.page_range, item.copies, self.paper_size, self.orientation)
                success += 1
                self.events.put(("status", (item.key, "已入队", str(data["id"]))))
            except (ServiceError, ValueError, OSError, RuntimeError) as exc:
                self.events.put(("status", (item.key, f"提交失败：{exc}", "")))
        self.events.put(("batch_done", success))

    def _poll_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "status":
                    key, status, job_id = payload
                    item = self._find_item(key)
                    if item:
                        item.status, item.job_id = status, job_id
                        self._render_items()
                elif event == "batch_done":
                    self.start_button.configure(state="normal")
                    self._show_message(f"已提交 {payload} 个打印任务", error=payload == 0)
                    self._refresh_history()
        except Empty:
            pass
        self.root.after(100, self._poll_events)

    def _auto_refresh(self) -> None:
        self._refresh_history()
        self.root.after(5000, self._auto_refresh)

    def _refresh_history(self) -> None:
        try:
            jobs = self.runtime.list_recent_jobs()
        except Exception as exc:
            self._show_message(f"任务刷新失败：{exc}", error=True)
            return
        for child in self.history.get_children():
            self.history.delete(child)
        for job in jobs:
            created_at = str(job.get("created_at") or "").replace("T", " ")[:19]
            self.history.insert("", "end", values=(job["source_filename"], job["printer_name"], STATUS_LABELS.get(str(job["status"]), job["status"]), created_at))

    def _find_item(self, key: str) -> BatchItem | None:
        return next((item for item in self.items if item.key == key), None)

    def _show_message(self, text: str, error: bool = False) -> None:
        self.message.configure(text=text, foreground="#b42318" if error else "#087443")

    def close(self) -> None:
        self._finish_edit()
        self.runtime.stop()
        self.root.destroy()
