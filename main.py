from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from app_core import DesktopRuntime
from desktop_app import DesktopApp


def main() -> None:
    try:
        runtime = DesktopRuntime()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("批量打印启动失败", str(exc))
        root.destroy()
        raise
    root = tk.Tk()
    DesktopApp(root, runtime)
    root.mainloop()


if __name__ == "__main__":
    main()
