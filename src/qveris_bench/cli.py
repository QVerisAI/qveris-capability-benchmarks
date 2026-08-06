import asyncio
import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, cast

import typer

from qveris_bench.catalog.service import CapCatalogService
from qveris_bench.catalog.validation import CapValidationError
from qveris_bench.execution.orchestrator import CellExecutionResult, RunOrchestrator
from qveris_bench.execution.resume import RunStateStore
from qveris_bench.models.enums import CellState, QualificationDisposition
from qveris_bench.models.provider import QualificationDecision
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.models.schema_export import check_schemas, export_schemas
from qveris_bench.providers.repository import (
    ProviderRegistryRepository,
    ProviderValidationError,
    qualify_provider_file,
)
from qveris_bench.suites.compiler import (
    CompiledSuite,
    compile_suite,
    write_frozen_suite,
    write_run_plan,
)

app = typer.Typer(
    name="qveris-bench",
    help="QVeris capability benchmark CLI (qveris-bench).",
    no_args_is_help=True,
)
schema_app = typer.Typer(help="Export and verify benchmark JSON Schemas.")
cap_app = typer.Typer(help="Inspect and validate CAP definitions.")
provider_app = typer.Typer(help="Validate and qualify Provider Access Paths.")
suite_app = typer.Typer(help="Freeze suites and compile Run Plans.")
app.add_typer(schema_app, name="schema")
app.add_typer(cap_app, name="cap")
app.add_typer(provider_app, name="provider")
app.add_typer(suite_app, name="suite")


@app.callback()
def main() -> None:
    """Run QVeris capability benchmarks."""


@cap_app.command("list")
def cap_list(
    root: Annotated[Path, typer.Option(help="CAP Pack root directory.")] = Path(
        "cap_packs"
    ),
) -> None:
    """List validated CAP definitions."""
    try:
        caps = CapCatalogService().list(root)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for cap in caps:
        typer.echo(f"{cap.cap_id}@{cap.version}\t{cap.name}")


@cap_app.command("validate")
def cap_validate(path: Path) -> None:
    """Validate one CAP definition."""
    try:
        cap = CapCatalogService().validate(path)
    except CapValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Valid CAP: {cap.cap_id}@{cap.version}")


@provider_app.command("validate")
def provider_validate(path: Path) -> None:
    """Validate one Provider and its Access Paths."""
    try:
        record = ProviderRegistryRepository(path.parent).load(path)
    except ProviderValidationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Valid Provider: {record.provider_id} "
        f"({len(record.access_paths)} access paths)"
    )


@provider_app.command("qualify")
def provider_qualify(
    path: Path,
    access_path_id: Annotated[
        str, typer.Option(help="Access Path receiving the terminal decision.")
    ],
    disposition: Annotated[
        QualificationDisposition, typer.Option(help="Terminal cohort disposition.")
    ],
    reason: Annotated[str, typer.Option(help="Evidence-based decision reason.")],
    evidence_digest: Annotated[str, typer.Option(help="SHA-256 evidence reference.")],
) -> None:
    """Record a terminal Provider qualification decision."""
    try:
        decision = QualificationDecision(
            disposition=disposition,
            reason=reason,
            evidence_digest=evidence_digest,
        )
        record = qualify_provider_file(path, access_path_id, decision)
    except (ValueError, ProviderValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Qualified Provider: {record.provider_id} -> {disposition.value}")


@provider_app.command("cohort-check")
def provider_cohort_check(
    root: Annotated[Path, typer.Option(help="Provider registry root.")] = Path(
        "providers"
    ),
) -> None:
    """Verify every Provider has a terminal cohort disposition."""
    try:
        records = ProviderRegistryRepository(root).cohort_check()
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Frozen cohort: {len(records)} provider(s)")


def _compile_suite_from_cli(
    suite_path: Path, cases: Path | None, providers_root: Path, cap: Path | None
) -> CompiledSuite:
    cases_path = cases or suite_path.with_name("cases.yaml")
    try:
        return compile_suite(suite_path, cases_path, providers_root, cap)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@suite_app.command("freeze")
def suite_freeze(
    suite_path: Path,
    cases: Annotated[Path | None, typer.Option(help="Cases YAML path.")] = None,
    cap: Annotated[Path | None, typer.Option(help="CAP definition YAML path.")] = None,
    providers_root: Annotated[
        Path, typer.Option(help="Provider registry root.")
    ] = Path("providers"),
    output: Annotated[Path | None, typer.Option(help="Frozen suite output.")] = None,
) -> None:
    """Freeze resolved suite inputs and write their fingerprint."""
    compiled = _compile_suite_from_cli(suite_path, cases, providers_root, cap)
    output_path = output or suite_path.with_name("suite.frozen.json")
    write_frozen_suite(compiled, output_path)
    typer.echo(f"Frozen suite {compiled.fingerprint} -> {output_path}")


@suite_app.command("plan")
def suite_plan(
    suite_path: Path,
    cases: Annotated[Path | None, typer.Option(help="Cases YAML path.")] = None,
    cap: Annotated[Path | None, typer.Option(help="CAP definition YAML path.")] = None,
    providers_root: Annotated[
        Path, typer.Option(help="Provider registry root.")
    ] = Path("providers"),
    output: Annotated[Path | None, typer.Option(help="Run Plan output.")] = None,
) -> None:
    """Expand a frozen suite into deterministic run cells."""
    compiled = _compile_suite_from_cli(suite_path, cases, providers_root, cap)
    output_path = output or suite_path.with_name("run-plan.json")
    write_run_plan(compiled, output_path)
    applicable = sum(cell.applicable for cell in compiled.run_plan.cells)
    typer.echo(
        f"Planned {len(compiled.run_plan.cells)} cells, "
        f"{applicable} applicable calls -> {output_path}"
    )


def _load_executor(reference: str) -> Callable[[RunCell], object]:
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("executor must use module:function notation")
    executor = getattr(importlib.import_module(module_name), attribute)
    if not callable(executor):
        raise ValueError("executor reference is not callable")
    return cast(Callable[[RunCell], object], executor)


async def _run_plan(
    plan: RunPlan, state_path: Path, executor_reference: str
) -> dict[str, CellState]:
    executor = _load_executor(executor_reference)

    async def execute(cell: RunCell) -> CellExecutionResult:
        result = executor(cell)
        if hasattr(result, "__await__"):
            result = await result
        if not isinstance(result, CellExecutionResult):
            raise ValueError("executor must return CellExecutionResult")
        return result

    return await RunOrchestrator(RunStateStore(state_path), execute).run(plan)


@app.command("run")
def run_execute(
    plan_path: Path,
    executor: Annotated[str, typer.Option(help="Async executor as module:function.")],
    state: Annotated[Path | None, typer.Option(help="Run state JSON path.")] = None,
) -> None:
    """Execute a frozen plan with an explicit provider executor."""
    try:
        plan = RunPlan.model_validate_json(plan_path.read_text())
        state_path = state or plan_path.with_name("state.json")
        states = asyncio.run(_run_plan(plan, state_path, executor))
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Run completed: {len(states)} state entries -> {state_path}")


@app.command("resume")
def run_resume(
    plan_path: Path,
    executor: Annotated[str, typer.Option(help="Async executor as module:function.")],
    state: Annotated[Path | None, typer.Option(help="Run state JSON path.")] = None,
) -> None:
    """Resume only infra-blocked cells of a matching frozen plan."""
    run_execute(plan_path, executor, state)


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
