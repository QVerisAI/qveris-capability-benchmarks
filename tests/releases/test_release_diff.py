from qveris_bench.releases.diff import diff_releases


def test_ac4_release_diff_reports_changed_top_level_sections() -> None:
    changed = diff_releases(
        {"release": {"version": "1.0.0"}, "cells": []},
        {"release": {"version": "1.0.1"}, "cells": []},
    )

    assert changed == ("release",)
