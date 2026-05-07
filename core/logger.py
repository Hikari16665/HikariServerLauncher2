import os
import sys
from enum import Enum
from rich.console import Console
from rich.theme import Theme
from rich.logging import RichHandler
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
import logging

BANNER = r"""
    __  ___ __              _   _____
   / / / (_) /______ ______(_) / ___/___  ______   _____  _____
  / /_/ / / //_/ __ `/ ___/ /  \__ \/ _ \/ ___/ | / / _ \/ ___/
 / __  / / ,< / /_/ / /  / /  ___/ /  __/ /   | |/ /  __/ /
/_/ /_/_/_/|_|\__,_/_/  /_/  /____/\___/_/    |___/\___/_/
   / /   ____ ___  ______  _____/ /_  ___  _____   |__ \
  / /   / __ `/ / / / __ \/ ___/ __ \/ _ \/ ___/   __/ /
 / /___/ /_/ / /_/ / / / / /__/ / / /  __/ /      / __/
/_____/\__,_/\__,_/_/ /_/\___/_/ /_/\___/_/      /____/
"""


custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "critical": "bold white on red",
    "debug": "dim",
    "key": "bold magenta",
})


class LogLevel(Enum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Logger:
    _instance = None
    _console = None
    _rich_handler = None
    _python_logger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._console = Console(theme=custom_theme, stderr=True)
            self._error_count = 0
            self._warning_count = 0
            self._setup_python_logger()
            self._initialized = True

    def _get_log_dir(self):
        """Get log directory, using cwd in frozen mode, project root in dev mode."""
        if getattr(sys, "frozen", False):
            log_dir = os.path.join(os.getcwd(), "logs")
        else:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def _setup_python_logger(self):
        self._python_logger = logging.getLogger("hsl2")
        self._python_logger.setLevel(logging.DEBUG)
        self._python_logger.handlers.clear()

        # Rich handler for stderr
        self._rich_handler = RichHandler(
            console=self._console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
        )
        self._rich_handler.setLevel(logging.DEBUG)
        self._python_logger.addHandler(self._rich_handler)

        # File handler — all logs
        log_dir = self._get_log_dir()
        all_handler = logging.FileHandler(
            os.path.join(log_dir, "hsl.log"), encoding="utf-8"
        )
        all_handler.setLevel(logging.DEBUG)
        all_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._python_logger.addHandler(all_handler)

        # File handler — errors and warnings only
        err_handler = logging.FileHandler(
            os.path.join(log_dir, "hsl-error.log"), encoding="utf-8"
        )
        err_handler.setLevel(logging.WARNING)
        err_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._python_logger.addHandler(err_handler)

    @property
    def console(self) -> Console:
        return self._console

    @property
    def error_count(self) -> int:
        return self._error_count

    @property
    def warning_count(self) -> int:
        return self._warning_count

    def debug(self, message: str, **kwargs):
        self._python_logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs):
        self._python_logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._warning_count += 1
        self._python_logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        self._error_count += 1
        self._python_logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._error_count += 1
        self._python_logger.critical(message, **kwargs)

    def success(self, message: str):
        self._console.print(f"[success]✓ {message}[/success]")

    def banner(self):
        self._console.print(BANNER)

    def key_generated(self, key: str):
        panel = Panel(
            f"[key]{key}[/key]",
            title="[bold yellow]⚠ Security Notice[/bold yellow]",
            border_style="yellow",
            padding=(1, 2)
        )
        self._console.print(panel)
        self._console.print(
            "[warning]A new admin key has been generated and saved to config.yml[/warning]"
        )

    def print_table(self, title: str, data: list, columns: list):
        table = Table(title=title, show_header=True, header_style="bold cyan")
        for col in columns:
            table.add_column(col)
        for row in data:
            table.add_row(*[str(cell) for cell in row])
        self._console.print(table)

    def print_panel(self, content: str, title: str = None, style: str = "cyan"):
        panel = Panel(content, title=title, border_style=style, padding=(1, 2))
        self._console.print(panel)

    def print_syntax(self, code: str, language: str = "python", title: str = None):
        syntax = Syntax(code, language, theme="monokai", line_numbers=True)
        if title:
            self._console.print(f"\n[bold]{title}[/bold]")
        self._console.print(syntax)

    def set_level(self, level: LogLevel):
        self._python_logger.setLevel(level.value)
