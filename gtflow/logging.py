
from rich.console import Console
from rich.theme import Theme

_custom_theme = Theme({
    "ok": "bold green",
    "warn": "bold yellow",
    "err": "bold red",
    "info": "cyan",
})

console = Console(theme=_custom_theme)
