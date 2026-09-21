from rich.console import Console
from rich.text import Text
import datetime

def timestamp() -> Text:
        return Text(datetime.datetime.now().isoformat(sep=" ", timespec="milliseconds"), style="dim italic")

class ConsoleLogger:
    def __init__(self, verbose: bool):
        self.verbose = verbose
        self.console = Console() 

    def log(self, text: str):
        if self.verbose: self.console.print(timestamp(), " INFO  ", text)

    def logerr(self, text: str):
        if self.verbose: self.console.print(timestamp(), " [red]ERROR[/red] ", text)

    def logwarn(self, text: str):
        if self.verbose: self.console.print(timestamp(), " [yellow]WARN[/yellow]  ", text)

    def logok(self, text: str):
        if self.verbose: self.console.print(timestamp(), "  [green]OK[/green]   ", text)

    def printjson(self, json: str):
        if self.verbose: self.console.print_json(json)