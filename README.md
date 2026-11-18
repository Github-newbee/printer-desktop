# Printer Desktop

Windows 桌面端批量 PDF 打印工具。最终用户只需要运行 `PrinterDesktop.exe`，不需要安装 Python、uv 或拉取源代码。

## 当前实现

- Tkinter 原生桌面界面，替代原 Flask 浏览器页面。
- 多选 PDF、递归添加文件夹、文件去重。
- 打印机读取使用 Windows `pywin32`。
- SQLite 任务记录、单线程打印队列、启动恢复、定时清理均保留。
- 使用项目内置 `tools/SumatraPDF.exe` 静默提交到 Windows 打印队列。
- 运行数据写入 `%LOCALAPPDATA%\PrinterDesktop`，不会写入安装目录。
- 支持纸张大小、方向、打印范围和份数。

## 开发机运行

```powershell
uv sync
uv run python main.py
```

开发机需要 Windows Python、uv、pywin32 和可用打印机；最终用户不需要这些开发依赖。

## 构建 EXE

```powershell
.\build.ps1
```

产物为 `dist\PrinterDesktop.exe`。构建脚本会把 `tools` 目录中的 SumatraPDF 及其 DLL 一起嵌入打包目录。

## 数据与日志

- 数据库：`%LOCALAPPDATA%\PrinterDesktop\data\print_service.db`
- 上传临时文件：`%LOCALAPPDATA%\PrinterDesktop\uploads`
- 日志：`%LOCALAPPDATA%\PrinterDesktop\logs\app.log`

可通过 `PRINTER_DESKTOP_DATA_DIR` 指定数据目录；可通过 `MAX_FILE_SIZE_MB`、`PRINT_COMMAND_TIMEOUT_SEC` 等环境变量调整运行参数。

## 发布前验收

1. 在目标 Windows 机器安装对应打印机驱动。
2. 用真实 PDF 添加多个文件，分别验证范围、份数、A4/A5、纵向/横向。
3. 验证打印机断开、Sumatra 缺失、超大文件、非 PDF 文件的错误提示。
4. 确认任务记录和日志目录具备写权限。
5. 确认成功状态表示“已提交到 Windows 打印队列”，不等于纸张已经完成输出。
