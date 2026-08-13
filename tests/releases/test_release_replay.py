from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from qveris_bench.models.cap import SourceReference
from qveris_bench.models.enums import (
    CellState,
    DisclosureLevel,
    LicenseStatus,
    RedactionStatus,
    RunMode,
    SourceType,
)
from qveris_bench.models.evidence import EvidenceBundle
from qveris_bench.models.release import BenchmarkRelease
from qveris_bench.models.run import RunCell, RunPlan
from qveris_bench.releases.builder import build_release
from qveris_bench.releases.canonical import canonical_release_bytes
from qveris_bench.releases.replay import ReleaseReplayError, replay_release_dir
from qveris_bench.suites.matrix import canonical_run_key


def test_ac3_replay_rejects_a_formal_release_when_public_harbor_contract_drifts(
    tmp_path: Path,
) -> None:
    contract = {"capability_id": "MKT.L1.RT", "contract_version": 1}
    contracts = [{"capability_id": "MKT.L1.RT", "contract": contract}]
    contracts_bytes = canonical_release_bytes(contracts)
    contract_digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source = SourceReference(
        source_type=SourceType.HARBOR_CATALOG,
        harbor_capability_id="MKT.L1.RT",
        contract_version=1,
        catalog_snapshot_digest=hashlib.sha256(contracts_bytes).hexdigest(),
        contract_digest=contract_digest,
    )
    contracts_path = tmp_path / "harbor_catalog" / "contracts.json"
    contracts_path.parent.mkdir()
    contracts_path.write_bytes(contracts_bytes)
    (contracts_path.parent / "catalog.json").write_bytes(
        canonical_release_bytes({"total": 1, "items": [{"capability_id": "MKT.L1.RT"}]})
    )
    (contracts_path.parent / "meta.json").write_bytes(
        canonical_release_bytes(
            {
                "origin": "https://harbor.qveris.cloud",
                "exporter_version": "1.0.0",
                "catalog_snapshot_digest": source.catalog_snapshot_digest,
                "counts": {"catalog": 1, "contracts": 1, "errors": 0},
                "contracts": [
                    {
                        "capability_id": "MKT.L1.RT",
                        "contract_version": 1,
                        "contract_digest": contract_digest,
                    }
                ],
            }
        )
    )
    planned_cell = RunCell(
        run_key=canonical_run_key(
            "quote-suite",
            "a" * 64,
            case_id="quote-case",
            provider_id="provider",
            access_path_id="provider-api",
            mode=RunMode.DIRECT,
            round_number=1,
        ),
        case_id="quote-case",
        provider_id="provider",
        access_path_id="provider-api",
        mode="direct",
        round=1,
        state=CellState.PLANNED,
    )
    plan = RunPlan(
        suite_id="quote-suite",
        suite_fingerprint="a" * 64,
        cap_id="stock-quote",
        cap_version="1.0.0",
        cap_sources=(source,),
        cells=(planned_cell,),
    )
    plan_bytes = canonical_release_bytes(plan.model_dump(mode="json"))
    cell = planned_cell.model_copy(update={"state": CellState.COMPLETED})
    evidence = EvidenceBundle(
        evidence_id="quote-evidence",
        run_key=cell.run_key,
        raw_digest="sha256:" + "b" * 64,
        public_digest="sha256:" + "c" * 64,
        redaction_status=RedactionStatus.SANITIZED,
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        extractor_version="1.0.0",
        suite_fingerprint="a" * 64,
    )
    release = BenchmarkRelease(
        release_id="quote-release",
        version="1.0.0",
        suite_fingerprint="a" * 64,
        run_plan_digest="sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
        evidence_ids=(evidence.evidence_id,),
        cap_id="stock-quote",
        cap_version="1.0.0",
        cap_sources=(source,),
    )
    release_dir = tmp_path / "releases" / release.release_id
    release_dir.mkdir(parents=True)
    (release_dir / "release-input.json").write_bytes(
        canonical_release_bytes(release.model_dump(mode="json"))
    )
    (release_dir / "run-plan.json").write_bytes(plan_bytes)
    (release_dir / "cells.json").write_bytes(
        canonical_release_bytes([cell.model_dump(mode="json")])
    )
    (release_dir / "evidence.json").write_bytes(
        canonical_release_bytes([evidence.model_dump(mode="json")])
    )
    release_bytes = build_release(
        release, (cell,), (evidence,), require_attribution=False
    )
    (release_dir / "release.json").write_bytes(release_bytes)

    replay_release_dir(release_dir, harbor_contracts_path=contracts_path)
    contracts_path.write_bytes(canonical_release_bytes([]))

    with pytest.raises(ReleaseReplayError, match="Harbor CAP provenance"):
        replay_release_dir(release_dir, harbor_contracts_path=contracts_path)


def test_ac3_replay_uses_the_content_addressed_harbor_snapshot(
    tmp_path: Path,
) -> None:
    contract = {"capability_id": "MKT.L1.RT", "contract_version": 1}
    contracts = [{"capability_id": "MKT.L1.RT", "contract": contract}]
    contracts_bytes = canonical_release_bytes(contracts)
    snapshot_digest = hashlib.sha256(contracts_bytes).hexdigest()
    contract_digest = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    source = SourceReference(
        source_type=SourceType.HARBOR_CATALOG,
        harbor_capability_id="MKT.L1.RT",
        contract_version=1,
        catalog_snapshot_digest=snapshot_digest,
        contract_digest=contract_digest,
    )
    catalog_root = tmp_path / "harbor_catalog"
    snapshot_root = catalog_root / "snapshots" / snapshot_digest
    snapshot_root.mkdir(parents=True)
    for directory in (catalog_root, snapshot_root):
        (directory / "catalog.json").write_bytes(
            canonical_release_bytes(
                {"total": 1, "items": [{"capability_id": "MKT.L1.RT"}]}
            )
        )
        (directory / "contracts.json").write_bytes(contracts_bytes)
        (directory / "meta.json").write_bytes(
            canonical_release_bytes(
                {
                    "origin": "https://harbor.qveris.cloud",
                    "exporter_version": "1.0.0",
                    "catalog_snapshot_digest": snapshot_digest,
                    "counts": {"catalog": 1, "contracts": 1, "errors": 0},
                    "contracts": [
                        {
                            "capability_id": "MKT.L1.RT",
                            "contract_version": 1,
                            "contract_digest": contract_digest,
                        }
                    ],
                }
            )
        )
    planned = RunCell(
        run_key=canonical_run_key(
            "quote-suite",
            "a" * 64,
            case_id="quote-case",
            provider_id="provider",
            access_path_id="provider-api",
            mode=RunMode.DIRECT,
            round_number=1,
        ),
        case_id="quote-case",
        provider_id="provider",
        access_path_id="provider-api",
        mode=RunMode.DIRECT,
        round=1,
        state=CellState.PLANNED,
    )
    plan = RunPlan(
        suite_id="quote-suite",
        suite_fingerprint="a" * 64,
        cap_id="stock-quote",
        cap_version="1.0.0",
        cap_sources=(source,),
        cells=(planned,),
    )
    plan_bytes = canonical_release_bytes(plan.model_dump(mode="json"))
    terminal = planned.model_copy(update={"state": CellState.COMPLETED})
    evidence = EvidenceBundle(
        evidence_id="quote-evidence",
        run_key=terminal.run_key,
        raw_digest="sha256:" + "b" * 64,
        public_digest="sha256:" + "c" * 64,
        redaction_status=RedactionStatus.SANITIZED,
        disclosure_level=DisclosureLevel.SANITIZED_PUBLIC,
        license_status=LicenseStatus.CLEARED,
        extractor_version="1.0.0",
        suite_fingerprint="a" * 64,
    )
    release = BenchmarkRelease(
        release_id="quote-release",
        version="1.0.0",
        suite_fingerprint="a" * 64,
        run_plan_digest="sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
        evidence_ids=(evidence.evidence_id,),
        cap_id="stock-quote",
        cap_version="1.0.0",
        cap_sources=(source,),
    )
    release_dir = tmp_path / "releases" / release.release_id
    release_dir.mkdir(parents=True)
    (release_dir / "release-input.json").write_bytes(
        canonical_release_bytes(release.model_dump(mode="json"))
    )
    (release_dir / "run-plan.json").write_bytes(plan_bytes)
    (release_dir / "cells.json").write_bytes(
        canonical_release_bytes([terminal.model_dump(mode="json")])
    )
    (release_dir / "evidence.json").write_bytes(
        canonical_release_bytes([evidence.model_dump(mode="json")])
    )
    (release_dir / "release.json").write_bytes(
        build_release(release, (terminal,), (evidence,))
    )
    (catalog_root / "contracts.json").write_bytes(canonical_release_bytes([]))

    replay_release_dir(
        release_dir, harbor_contracts_path=catalog_root / "contracts.json"
    )
