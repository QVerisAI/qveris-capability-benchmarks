# Release replay

An independent operator may reproduce a release only from the frozen suite,
run-plan, authorized public evidence, and immutable release inputs. Raw artifacts
and credential values remain outside this repository.

## Prerequisites

Use Python 3.12 and the locked dependency set. Do not add provider credentials to
the repository or use a personal developer key. Replaying a release must not invoke
provider APIs, MCP servers, or an Agent backend.

## Procedure

1. Check out the release commit and run `uv sync --locked --all-groups`.
2. Run `uv run qveris-bench release verify RELEASE.json --digest DIGEST`.
3. Rebuild the bundle from the release manifest, terminal cells, and authorized
   public evidence with `qveris-bench release build`.
4. Compare the resulting canonical digest with the published digest.
5. Run the local quality commands in `CONTRIBUTING.md` before reporting the result.

If a digest differs, preserve the inputs and report the mismatch. Do not edit a
published release, regenerate private evidence, or assign a provider conclusion.
