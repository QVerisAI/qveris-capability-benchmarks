#!/usr/bin/env python3
"""Run a new CRYPTO.SPOT.RT edition and publish sanitized evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from qveris_bench.cap_packs.crypto_spot_quote.direct import Terminal, evaluate
from qveris_bench.cap_packs.crypto_spot_quote.runner import (
    assert_new_release_paths,
    assert_publishable_terminal_matrix,
    request_for_cell,
)
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.credentials import load_qveris_api_key
from qveris_bench.execution.qveris import (
    QverisToolClient,
    execute_discovered_tool,
    gateway_metrics,
)
from qveris_bench.models.enums import (
    CellState,
    DisclosureLevel,
    FailureAttribution,
    LicenseStatus,
    RedactionStatus,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import canonical_release_bytes
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs" / "crypto-spot-quote"


def _release_paths(release_id: str) -> tuple[Path, Path]:
    if not release_id or Path(release_id).name != release_id:
        raise ValueError("release ID must be a single immutable path name")
    return ROOT / "evidence" / release_id, ROOT / "releases" / release_id


async def run(release_id: str) -> None:
    public_root, release_root = _release_paths(release_id)
    assert_new_release_paths(public_root, release_root)
    compiled = compile_suite(
        PACK / "suite.yaml",
        PACK / "cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
        ROOT / "harbor_catalog" / "contracts.json",
    )
    raw_root = Path("/private/tmp") / release_id / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    client = QverisToolClient(
        httpx.AsyncClient(timeout=60),
        RawArtifactStore(raw_root, ROOT),
        load_qveris_api_key(),
    )
    records: list[tuple[RunCell, Terminal, str, float | None]] = []
    try:
        for cell in compiled.run_plan.cells:
            tool_id, parameters = request_for_cell(
                cell.provider_id, cell.access_path_id, cell.case_id
            )
            request_parameters: dict[str, object] = {}
            for key, value in parameters.items():
                request_parameters[key] = value
            execution = await execute_discovered_tool(
                client, f"{cell.run_key}-search", tool_id, tool_id, request_parameters
            )
            document = json.loads(execution.result.raw_path.read_text(encoding="utf-8"))
            response = document.get("result")
            if not isinstance(response, dict):
                response = {"status_code": execution.result.status_code, "data": None}
            latency_ms, _ = gateway_metrics(document)
            records.append(
                (
                    cell,
                    evaluate(cell.provider_id, cell.case_id, response),
                    execution.result.raw_digest,
                    latency_ms,
                )
            )
    finally:
        await client.close()

    assert_publishable_terminal_matrix(
        tuple((cell.case_id, terminal.state) for cell, terminal, _, _ in records)
    )
    public_store = PublicArtifactStore(public_root)
    terminal_cells = []
    evidence = []
    manifest_entries = []
    for cell, terminal, raw_digest, latency_ms in records:
        public_document = {
            "run_key": cell.run_key,
            "case_id": cell.case_id,
            "round": cell.round,
            "state": terminal.state.value,
            "failure_attribution": (
                terminal.attribution.value if terminal.attribution else None
            ),
            "raw_digest": raw_digest,
            "gateway_latency_ms": latency_ms,
            "facts": terminal.facts,
        }
        artifact = public_store.persist(
            cell.run_key.replace(":", "-"), canonical_release_bytes(public_document)
        )
        evidence_id = f"{cell.provider_id}-{cell.case_id}-round-{cell.round}"
        terminal_cells.append(
            cell.model_copy(
                update={
                    "state": CellState(terminal.state),
                    "failure_attribution": (
                        FailureAttribution(terminal.attribution)
                        if terminal.attribution
                        else None
                    ),
                }
            )
        )
        evidence.append(
            EvidenceBundle(
                evidence_id=evidence_id,
                run_key=cell.run_key,
                raw_digest=raw_digest,
                public_digest=artifact.digest,
                redaction_status=RedactionStatus.SANITIZED,
                disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
                license_status=LicenseStatus.CLEARED,
                extractor_version="1.0.0",
                suite_fingerprint=compiled.fingerprint,
                latency_ms=latency_ms,
            )
        )
        manifest_entries.append(
            {
                "evidence_id": evidence_id,
                "run_key": cell.run_key,
                "path": artifact.path.relative_to(ROOT).as_posix(),
                "public_digest": artifact.digest,
            }
        )

    plan_bytes = canonical_release_bytes(compiled.run_plan.model_dump(mode="json"))
    release = BenchmarkRelease(
        release_id=release_id,
        version="1.0.0",
        suite_fingerprint=compiled.fingerprint,
        run_plan_digest=sha256_digest(plan_bytes),
        evidence_ids=tuple(item.evidence_id for item in evidence),
        cap_id="crypto-spot-quote",
        cap_version="1.0.0",
        cap_sources=compiled.run_plan.cap_sources,
        limitations=(
            "Two QVeris Access Paths; no native exchange API is tested.",
            "The positive sample is BTC/USDT spot only, not broad pair coverage.",
            "24-hour windows are exchange-defined and not a common market bar.",
        ),
    )
    release_root.mkdir(parents=True, exist_ok=False)
    release_input = canonical_release_bytes(release.model_dump(mode="json"))
    cells_json = canonical_release_bytes(
        [cell.model_dump(mode="json") for cell in terminal_cells]
    )
    evidence_json = canonical_release_bytes(
        [item.model_dump(mode="json") for item in evidence]
    )
    manifest_json = canonical_release_bytes(
        {"release_id": release_id, "evidence": manifest_entries}
    )
    (release_root / "release-input.json").write_bytes(release_input)
    (release_root / "run-plan.json").write_bytes(plan_bytes)
    (release_root / "cells.json").write_bytes(cells_json)
    (release_root / "evidence.json").write_bytes(evidence_json)
    (public_root / "manifest.json").write_bytes(manifest_json)
    (release_root / "public-evidence-manifest.json").write_bytes(manifest_json)
    (release_root / "release.json").write_bytes(
        build_release(release, tuple(terminal_cells), tuple(evidence))
    )
    print(f"Built {release_id}: {len(evidence)} sanitized evidence records")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(run(parse_args().release_id))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
