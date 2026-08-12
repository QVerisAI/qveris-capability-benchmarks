from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

from qveris_bench.evidence.hashing import sha256_digest
from qveris_bench.models.base import EvidenceRef

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "31572117228"
EVIDENCE = ROOT / "evidence/dividend-events-market-coverage-2026-q3-v1"
OUTPUT = (
    ROOT / "releases/dividend-events-market-coverage-2026-q3-v1/github-artifacts.json"
)


class GitHubRun(BaseModel):
    id: int
    head_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    status: str
    conclusion: str


class GitHubArtifact(BaseModel):
    id: int
    name: str
    digest: EvidenceRef
    expired: bool


class GitHubArtifactsResponse(BaseModel):
    total_count: int
    artifacts: tuple[GitHubArtifact, ...]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-root", type=Path)
    args = parser.parse_args(argv)
    run = GitHubRun.model_validate(
        _github_json(
            f"repos/QVerisAI/qveris-capability-benchmarks/actions/runs/{RUN_ID}"
        )
    )
    response = GitHubArtifactsResponse.model_validate(
        _github_json(
            f"repos/QVerisAI/qveris-capability-benchmarks/actions/runs/{RUN_ID}/artifacts?per_page=100"
        )
    )
    if (
        run.id != int(RUN_ID)
        or run.status != "completed"
        or run.conclusion != "success"
    ):
        raise ValueError("GitHub run is not a successful completed run")
    if response.total_count != len(response.artifacts):
        raise ValueError("GitHub artifact response is incomplete")
    if any(item.expired for item in response.artifacts):
        raise ValueError("GitHub artifact has expired")
    names = [item.name for item in response.artifacts]
    if len(names) != len(set(names)):
        raise ValueError("GitHub artifact names are not unique")

    if args.download_root is not None:
        _export(run, response.artifacts, args.download_root)
        return
    with tempfile.TemporaryDirectory(prefix="qveris-market-artifacts-") as directory:
        download_root = Path(directory)
        subprocess.run(
            ["gh", "run", "download", RUN_ID, "-D", str(download_root)],
            check=True,
        )
        _export(run, response.artifacts, download_root)


def _export(
    run: GitHubRun,
    api_artifacts: tuple[GitHubArtifact, ...],
    download_root: Path,
) -> None:
    artifact_index = {item.name: item for item in api_artifacts}
    artifacts = []
    terminal_shas = set()
    for local_path in sorted(EVIDENCE.glob("*.json")):
        name = f"dividend-market-{local_path.stem}"
        artifact = artifact_index.pop(name)
        terminal_paths = tuple((download_root / name).glob("*terminal*.json"))
        if len(terminal_paths) != 1:
            raise ValueError("GitHub artifact must contain exactly one terminal")
        remote_bytes = terminal_paths[0].read_bytes()
        if remote_bytes != local_path.read_bytes():
            raise ValueError("public terminal differs from GitHub artifact")
        terminal = TypeAdapter(dict[str, object]).validate_json(remote_bytes)
        github_sha = terminal.get("github_sha")
        raw_digest = terminal.get("raw_digest")
        if not isinstance(github_sha, str) or not isinstance(raw_digest, str):
            raise ValueError("GitHub terminal provenance is missing")
        terminal_shas.add(github_sha)
        artifacts.append(
            {
                "id": artifact.id,
                "name": name,
                "digest": artifact.digest,
                "public_digest": sha256_digest(remote_bytes),
                "raw_digest": raw_digest,
            }
        )
    if artifact_index or len(terminal_shas) != 1:
        raise ValueError("GitHub artifact topology or terminal SHA mismatch")
    document = {
        "github_run_id": RUN_ID,
        "github_sha": next(iter(terminal_shas)),
        "github_head_sha": run.head_sha,
        "artifacts": artifacts,
    }
    OUTPUT.write_text(json.dumps(document, indent=2) + "\n")


def _github_json(endpoint: str) -> object:
    return json.loads(subprocess.check_output(["gh", "api", endpoint]))


if __name__ == "__main__":
    main()
