from pathlib import Path
from typing import Annotated

import typer

from qveris_bench.models.schema_export import check_schemas, export_schemas

app = typer.Typer(
    name="qveris-bench",
    help="QVeris capability benchmark CLI (qveris-bench).",
    no_args_is_help=True,
)
schema_app = typer.Typer(help="Export and verify benchmark JSON Schemas.")
app.add_typer(schema_app, name="schema")


@app.callback()
def main() -> None:
    """Run QVeris capability benchmarks."""


@schema_app.command("export")
def schema_export(
    output_dir: Annotated[Path, typer.Option(help="Schema output directory.")] = Path(
        "schemas"
    ),
    check: Annotated[
        bool, typer.Option("--check", help="Fail when schemas drift.")
    ] = False,
) -> None:
    """Export canonical JSON Schemas or verify committed copies."""
    if check:
        if not check_schemas(output_dir):
            typer.echo(f"Schema drift detected in {output_dir}", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"Schemas verified in {output_dir}")
        return

    exported = export_schemas(output_dir)
    typer.echo(f"Exported {len(exported)} schemas to {output_dir}")


if __name__ == "__main__":
    app()
