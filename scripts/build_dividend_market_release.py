from __future__ import annotations

from pathlib import Path

from qveris_bench.execution.direct_binding import (
    direct_binding_registry_digest,
    load_direct_binding_registry,
)
from qveris_bench.releases.canonical import release_digest
from qveris_bench.releases.public_terminal import assemble_public_terminal_release
from qveris_bench.suites.compiler import compile_suite

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "cap_packs/dividend_events"
RELEASE_ID = "dividend-events-market-coverage-2026-q3-v1"
PUBLIC_EVIDENCE = ROOT / "evidence" / RELEASE_ID
OUTPUT = ROOT / "releases" / RELEASE_ID
LIMITATIONS = (
    "Coverage is measured per Provider and Access Path using one fixed "
    "representative symbol per market over 2024-01-01 through 2026-07-31; "
    "it is not a provider-wide market guarantee.",
    "Each applicable Direct cell ran twice. A market is supported only when "
    "both rounds completed with the required dividend-event fields and "
    "verified request identity.",
    "Explicitly unsupported QVeris markets and markets outside an Access "
    "Path contract are not called again; they remain not_applicable with "
    "the frozen reason in the run plan.",
    "Offline replay verifies the published artifacts and release bytes. It "
    "does not call providers or prove their current behavior.",
)


def main() -> None:
    registry_path = PACK / "market-direct-bindings.json"
    compiled = compile_suite(
        PACK / "market-suite.yaml",
        PACK / "market-cases.yaml",
        ROOT / "providers",
        PACK / "cap.yaml",
    )
    artifacts = assemble_public_terminal_release(
        compiled=compiled,
        binding_registry=load_direct_binding_registry(registry_path),
        binding_registry_digest=direct_binding_registry_digest(registry_path),
        terminal_paths=tuple(sorted(PUBLIC_EVIDENCE.glob("*.json"))),
        release_id=RELEASE_ID,
        version="1.0.0",
        limitations=LIMITATIONS,
    )
    artifacts.write(OUTPUT)
    print(release_digest(artifacts.release_bytes))


if __name__ == "__main__":
    main()
