from __future__ import annotations

import json
import os
import platform
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "docs/guides/capability-seo/best-dividend-apis/manifest.yaml"
CRYPTO_PACKAGE = ROOT / (
    "docs/guides/capability-seo/best-crypto-spot-quote-apis/manifest.yaml"
)


def test_ac6_wheel_cli_reproduces_from_outside_the_repository(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(dist.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert "qveris_bench/assets/fonts/QVerisCharts-Regular.otf" in names
    assert "qveris_bench/assets/fonts/QVerisCharts-Bold.otf" in names

    environment = tmp_path / "venv"
    created = subprocess.run(
        ["uv", "venv", "--python", "3.12", str(environment)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert created.returncode == 0, created.stderr
    python = environment / "bin/python"
    installed = subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(wheel)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert installed.returncode == 0, installed.stderr

    outside = tmp_path / "outside"
    outside.mkdir()
    isolated_home = tmp_path / "home"
    isolated_home.mkdir()
    executable = environment / "bin/qveris-bench"
    for package in (PACKAGE, CRYPTO_PACKAGE):
        result = subprocess.run(
            [str(executable), "publication", "reproduce", "--package", str(package)],
            cwd=outside,
            check=False,
            capture_output=True,
            text=True,
            env={
                "PATH": str(environment / "bin"),
                "HOME": str(isolated_home),
                "NO_PROXY": "*",
            },
        )

        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["status"] == (
            "verified"
            if platform.system() == "Linux"
            else "verified_with_noncanonical_chart_bytes"
        )
    assert "QVERIS_API_KEY" not in os.environ
    assert list(isolated_home.iterdir()) == []
