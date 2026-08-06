import typer

app = typer.Typer(
    name="qveris-bench",
    help="QVeris capability benchmark CLI (qveris-bench).",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Run QVeris capability benchmarks."""


if __name__ == "__main__":
    app()
