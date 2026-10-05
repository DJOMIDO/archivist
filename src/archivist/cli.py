import typer

from archivist.config import get_settings

app = typer.Typer(
    help="Archivist: ask questions about your own documents.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Archivist: ask questions about your own documents."""


@app.command()
def config() -> None:
    """Show the effective configuration."""
    settings = get_settings()
    for name, value in settings.model_dump().items():
        typer.echo(f"{name} = {value}")
