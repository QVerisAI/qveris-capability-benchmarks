from __future__ import annotations

import json
import subprocess
from pathlib import Path

from qveris_bench.evidence.hashing import sha256_digest

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "31572117228"
EVIDENCE = ROOT / "evidence/dividend-events-market-coverage-2026-q3-v1"
OUTPUT = (
    ROOT / "releases/dividend-events-market-coverage-2026-q3-v1/github-artifacts.json"
)


def main() -> None:
    run = _github_json(
        f"repos/QVerisAI/qveris-capability-benchmarks/actions/runs/{RUN_ID}"
    )
    response = _github_json(
        f"repos/QVerisAI/qveris-capability-benchmarks/actions/runs/{RUN_ID}/artifacts?per_page=100"
    )
    api_artifacts = {item["name"]: item for item in response["artifacts"]}
    terminals = [
        json.loads(path.read_text()) for path in sorted(EVIDENCE.glob("*.json"))
    ]
    terminal_shas = {item["github_sha"] for item in terminals}
    if len(terminal_shas) != 1:
        raise ValueError("public terminals must share one GitHub SHA")
    artifacts = []
    for path, terminal in zip(sorted(EVIDENCE.glob("*.json")), terminals, strict=True):
        name = f"dividend-market-{path.stem}"
        artifact = api_artifacts.pop(name)
        artifacts.append(
            {
                "id": artifact["id"],
                "name": name,
                "digest": artifact["digest"],
                "public_digest": sha256_digest(path.read_bytes()),
                "raw_digest": terminal["raw_digest"],
            }
        )
    if api_artifacts:
        raise ValueError("GitHub run contains unexpected artifacts")
    document = {
        "github_run_id": RUN_ID,
        "github_sha": next(iter(terminal_shas)),
        "github_head_sha": run["head_sha"],
        "artifacts": artifacts,
    }
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n")


def _github_json(endpoint: str) -> dict[str, object]:
    content = subprocess.check_output(["gh", "api", endpoint])
    document = json.loads(content)
    if not isinstance(document, dict):
        raise ValueError("GitHub API returned an invalid document")
    return document


if __name__ == "__main__":
    main()
