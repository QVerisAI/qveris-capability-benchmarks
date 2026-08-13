#!/usr/bin/env python3
"""Run the frozen CRYPTO.SPOT.RT suite and publish sanitized evidence."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import httpx

from qveris_bench.cap_packs.crypto_spot_quote.direct import evaluate
from qveris_bench.cap_packs.crypto_spot_quote.runner import request_for_cell
from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.evidence.store import PublicArtifactStore, RawArtifactStore
from qveris_bench.execution.credentials import load_qveris_api_key
from qveris_bench.execution.qveris import QverisToolClient, gateway_metrics
from qveris_bench.models.enums import CellState, FailureAttribution
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import canonical_release_bytes
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs" / "crypto-spot-quote"
RELEASE_ID = "crypto-spot-quote-2026-q3-v1"
PUBLIC_ROOT = ROOT / "evidence" / RELEASE_ID
RELEASE_ROOT = ROOT / "releases" / RELEASE_ID


async def main() -> None:
    compiled = compile_suite(
        PACK / "suite.yaml",
        PACK / "cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
        ROOT / "harbor_catalog" / "contracts.json",
    )
    raw_root = Path("/private/tmp") / RELEASE_ID / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(PUBLIC_ROOT, ignore_errors=True)
    shutil.rmtree(RELEASE_ROOT, ignore_errors=True)
    public_store = PublicArtifactStore(PUBLIC_ROOT)
    client = QverisToolClient(
        httpx.AsyncClient(timeout=60),
        RawArtifactStore(raw_root, ROOT),
        load_qveris_api_key(),
    )
    terminal_cells = []
    evidence = []
    manifest_entries = []
    try:
        for cell in compiled.run_plan.cells:
            tool_id, parameters = request_for_cell(cell.provider_id, cell.case_id)
            search = await client.search(f"{cell.run_key}-search", tool_id, limit=5)
            result = await client.execute(
                f"{cell.run_key}-execute", tool_id, search.search_id, parameters
            )
            document = json.loads(result.raw_path.read_text(encoding="utf-8"))
            response = document.get("result")
            if not isinstance(response, dict):
                response = {"status_code": result.status_code, "data": None}
            latency_ms, _ = gateway_metrics(document)
            terminal = evaluate(cell.provider_id, cell.case_id, response)
            public_document = {
                "run_key": cell.run_key,
                "case_id": cell.case_id,
                "round": cell.round,
                "state": terminal.state.value,
                "failure_attribution": (
                    terminal.attribution.value if terminal.attribution else None
                ),
                "raw_digest": result.raw_digest,
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
                    raw_digest=result.raw_digest,
                    public_digest=artifact.digest,
                    redaction_status="sanitized",
                    disclosure_level="sanitized_public",
                    license_status="cleared",
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
    finally:
        await client.close()

    plan_bytes = canonical_release_bytes(compiled.run_plan.model_dump(mode="json"))
    release = BenchmarkRelease(
        release_id=RELEASE_ID,
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
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)
    release_input = canonical_release_bytes(release.model_dump(mode="json"))
    cells_json = canonical_release_bytes(
        [cell.model_dump(mode="json") for cell in terminal_cells]
    )
    evidence_json = canonical_release_bytes(
        [item.model_dump(mode="json") for item in evidence]
    )
    manifest_json = canonical_release_bytes(
        {"release_id": RELEASE_ID, "evidence": manifest_entries}
    )
    (RELEASE_ROOT / "release-input.json").write_bytes(release_input)
    (RELEASE_ROOT / "run-plan.json").write_bytes(plan_bytes)
    (RELEASE_ROOT / "cells.json").write_bytes(cells_json)
    (RELEASE_ROOT / "evidence.json").write_bytes(evidence_json)
    (PUBLIC_ROOT / "manifest.json").write_bytes(manifest_json)
    (RELEASE_ROOT / "public-evidence-manifest.json").write_bytes(manifest_json)
    (RELEASE_ROOT / "release.json").write_bytes(
        build_release(release, tuple(terminal_cells), tuple(evidence))
    )
    print(f"Built {RELEASE_ID}: {len(evidence)} sanitized evidence records")


if __name__ == "__main__":
    asyncio.run(main())
