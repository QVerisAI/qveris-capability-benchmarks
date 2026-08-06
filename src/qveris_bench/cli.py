import asyncio
import importlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, cast

import httpx
import typer

from qveris_bench.catalog.service import CapCatalogService
from qveris_bench.catalog.validation import CapValidationError
from qveris_bench.evidence.store import RawArtifactStore
from qveris_bench.execution.orchestrator import CellExecutionResult, RunOrchestrator
from qveris_bench.execution.qveris import QverisToolClient
from qveris_bench.execution.resume import RunStateStore
from qveris_bench.models.enums import CellState, QualificationDisposition
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.provider import QualificationDecision
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.models.schema_export import check_schemas, export_schemas
from qveris_bench.providers.repository import (
    ProviderRegistryRepository,
    ProviderValidationError,
    qualify_provider_file,
)
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.verify import verify_release
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
release_app = typer.Typer(help="Build and verify immutable benchmark releases.")
qveris_app = typer.Typer(help="Discover and execute frozen QVeris connector tools.")
app.add_typer(schema_app, name="schema")
app.add_typer(cap_app, name="cap")
app.add_typer(provider_app, name="provider")
app.add_typer(suite_app, name="suite")
app.add_typer(release_app, name="release")
app.add_typer(qveris_app, name="qveris")


@app.callback()
def main() -> None:
    """Run QVeris capability benchmarks."""


@qveris_app.command("search")
def qveris_search(
    query: Annotated[str, typer.Option(help="Capability query for tool discovery.")],
    limit: Annotated[int, typer.Option(min=1, max=50)] = 10,
    raw_artifact_dir: Annotated[
        Path | None,
        typer.Option(help="Private raw artifact directory outside the repo."),
    ] = None,
) -> None:
    """Run a QVeris tool search without executing a provider tool."""
    api_key = os.environ.get("QVERIS_API_KEY")
    raw_dir = raw_artifact_dir or _raw_artifact_dir_from_env()
    if not api_key:
        typer.echo("QVERIS_API_KEY is required", err=True)
        raise typer.Exit(code=1)
    if raw_dir is None:
        typer.echo("private raw artifact directory is required", err=True)
        raise typer.Exit(code=1)

    async def search() -> dict[str, object]:
        client = QverisToolClient(
            httpx.AsyncClient(),
            RawArtifactStore(raw_dir, Path.cwd()),
            api_key,
        )
        try:
            result = await client.search("qveris-search", query, limit)
            document = json.loads(result.result.raw_path.read_text(encoding="utf-8"))
            if not isinstance(document, dict):
                raise ValueError("QVeris search response must be an object")
            results = document.get("results", [])
            if not isinstance(results, list):
                raise ValueError("QVeris search results must be a list")
            tool_ids = tuple(
                item["tool_id"]
                for item in results
                if isinstance(item, dict) and isinstance(item.get("tool_id"), str)
            )
            description = (
                json.loads(
                    (
                        await client.describe_tools(
                            "qveris-tool-descriptions", tool_ids
                        )
                    ).raw_path.read_text(encoding="utf-8")
                )
                if tool_ids
                else {}
            )
        finally:
            await client.close()
        return {
            "result_count": len(results),
            "tools": [
                {
                    key: item.get(key)
                    for key in ("tool_id", "name", "description", "parameters")
                    if key in item
                }
                for item in results
                if isinstance(item, dict)
            ],
            "descriptions": description,
        }

    try:
        typer.echo(json.dumps(asyncio.run(search()), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _raw_artifact_dir_from_env() -> Path | None:
    value = os.environ.get("QVERIS_BENCH_RAW_ARTIFACT_DIR")
    return Path(value) if value else None


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


def _load_json_model_list(
    path: Path, model: type[RunCell] | type[EvidenceBundle]
) -> tuple[object, ...]:
    document = json.loads(path.read_text())
    if not isinstance(document, list):
        raise ValueError(f"{path} must contain a JSON array")
    return tuple(model.model_validate(item) for item in document)


@release_app.command("build")
def release_build(
    release_path: Path,
    cells_path: Path,
    evidence_path: Path,
    output: Annotated[Path, typer.Option(help="Immutable release JSON output.")],
) -> None:
    """Build an immutable release from validated machine-readable inputs."""
    try:
        release = BenchmarkRelease.model_validate_json(release_path.read_text())
        cells = _load_json_model_list(cells_path, RunCell)
        evidence = _load_json_model_list(evidence_path, EvidenceBundle)
        content = build_release(
            release,
            cast(tuple[RunCell, ...], cells),
            cast(tuple[EvidenceBundle, ...], evidence),
        )
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(content)
    typer.echo(f"Built release {release_digest(content)} -> {output}")


@release_app.command("verify")
def release_verify(path: Path, digest: Annotated[str, typer.Option()]) -> None:
    """Verify an immutable release against its canonical digest."""
    if not verify_release(path, digest):
        typer.echo("release digest mismatch", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Verified release {digest}")


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
