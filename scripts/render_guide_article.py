#!/usr/bin/env python3
# ruff: noqa: E501  # markdown content templates legitimately exceed 88 cols
"""Render a funnel-structured SEO article skeleton from raw probe evidence.

Inputs are the raw probe jsonl records (evidence/private) and the CAP
chart-data (supplier metadata + provider/question mapping). Records are
aggregated per provider so a question shared by several suppliers is not
double-counted. Output is a markdown skeleton with all data-derived tables,
numbers, and date anchors filled in; editorial sections (verdict rationale,
provider deep-dives, production limits) are left as TODO placeholders for a
human editor.

Usage:
    uv run python scripts/render_guide_article.py \
        --chart-data scripts/fixtures/dividend-chart-data.yaml \
        --guide-label "分红数据 API" --edition 2026-08-10 \
        --output /tmp/article-skeleton.md

Evidence jsonl paths default to evidence/private; pass --direct/--param/
--recovery/--interpret/--self-description to override.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"证据文件缺失: {path} —— 请先运行 probe runner 生成 evidence"
        )
    lines = [
        line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    parsed: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{index} 非法 JSON 行: {exc}") from exc
        if isinstance(value, dict):
            parsed.append(value)
    if not parsed:
        raise ValueError(f"{path} 没有任何有效记录，空证据不应产出空文章")
    return parsed


def load_chart_data(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"chart data is not a mapping: {path}")
    return loaded


def _provider_name(chart: dict[str, Any], provider_id: str) -> str:
    """Map provider_id -> supplier name via chart-data."""
    for supplier in chart["suppliers"]:
        if supplier["provider_id"] == provider_id:
            name = supplier.get("name")
            return name if isinstance(name, str) else provider_id
    return provider_id


def _provider_ids(records: list[dict[str, Any]]) -> set[str]:
    """Collect string provider ids from probe records (type-narrowing helper)."""
    ids: set[str] = set()
    for record in records:
        provider_id = record.get("provider_id")
        if isinstance(provider_id, str):
            ids.add(provider_id)
    return ids


def _warn_provider_mismatch(chart: dict[str, Any], data: dict[str, Any]) -> None:
    """Warn when chart suppliers and evidence providers diverge."""
    chart_ids = {s.get("provider_id") for s in chart.get("suppliers", [])}
    ev_ids: set[str] = set()
    for key in ("direct_test", "param_fill", "error_recovery", "self_description"):
        ev_ids.update(data.get(key, {}).keys())
    missing = chart_ids - ev_ids
    extra = ev_ids - chart_ids
    if missing:
        print(
            f"警告: chart 有 {len(missing)} 个供应商无任何证据: {sorted(missing)}",
            file=sys.stderr,
        )
    if extra:
        print(
            f"警告: evidence 有 {len(extra)} 个 provider 不在 chart: {sorted(extra)}",
            file=sys.stderr,
        )


def _latest_batch(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the newest recorded_at batch (probe files append over time)."""
    if not records:
        return []
    timestamps: list[str] = []
    for record in records:
        recorded_at = record.get("recorded_at")
        if isinstance(recorded_at, str):
            timestamps.append(recorded_at)
    if not timestamps:
        return records
    latest = max(timestamps)
    return [record for record in records if record.get("recorded_at") == latest]


def render_main_table(data: dict[str, Any], chart: dict[str, Any]) -> str:
    """Build the overview table from per-provider probe records."""
    rows: list[str] = [
        "| 供应商 | 实测延迟 | 单次费用 | Direct Test | AI 落参 | AI 自愈 | 自解释 | 市场侧重 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    direct = data["direct_test"]
    param = data["param_fill"]
    recovery = data["error_recovery"]
    sd = data["self_description"]

    for supplier in chart["suppliers"]:
        name = supplier["name"]
        provider = supplier["provider_id"]
        dt = direct.get(provider, {})
        latency = dt.get("avg_latency_ms")
        cost = dt.get("success_call_credits")

        # AI dimensions: aggregate per-provider (not per shared question)
        param_ok = param.get(provider, {}).get("passed", 0)
        param_tot = param.get(provider, {}).get("total", 0)
        recovery_ok = recovery.get(provider, {}).get("passed", 0)
        recovery_tot = recovery.get(provider, {}).get("total", 0)
        sd_record = sd.get(provider, {})
        sd_total = sd_record.get("total", 0)
        sd_denom = sd_record.get("denominator", 6)

        has_dt = bool(dt)
        has_param = bool(param.get(provider))
        has_recovery = bool(recovery.get(provider))
        latency_s = f"{latency / 1000:.1f}s" if latency is not None else "未测"
        cost_s = f"{cost:.2f}" if cost is not None else "未测"
        dt_s = f"{dt.get('passed', 0)}/{dt.get('total', 0)}" if has_dt else "未测"
        param_s = f"{param_ok}/{param_tot}" if has_param else "未测"
        recovery_s = f"{recovery_ok}/{recovery_tot}" if has_recovery else "未测"
        sd_s = f"{sd_total}/{sd_denom}" if sd_record else "未测"
        market = supplier.get("markets", [])
        market_s = market[0] if market else "—"
        rows.append(
            f"| {name} | {latency_s} | {cost_s} | {dt_s} | "
            f"{param_s} | {recovery_s} | {sd_s} | {market_s} |"
        )
    return "\n".join(rows)


def render_param_fill_table(data: dict[str, Any], chart: dict[str, Any]) -> str:
    rows = ["| 供应商 | 通过率 | 实测说明 |", "|---|---|---|"]
    for provider, info in sorted(data["param_fill"].items()):
        name = _provider_name(chart, provider)
        rows.append(
            f"| {name} | {info['passed']}/{info['total']} | <!-- TODO 实测说明 --> |"
        )
    return "\n".join(rows)


def render_recovery_table(data: dict[str, Any], chart: dict[str, Any]) -> str:
    rows = [
        "| 供应商 | 通过率 | 失败样本 | 失败根因 |",
        "|---|---|---|---|",
    ]
    for provider, info in sorted(data["error_recovery"].items()):
        name = _provider_name(chart, provider)
        rows.append(
            f"| {name} | {info['passed']}/{info['total']} | "
            "<!-- TODO 失败样本 --> | <!-- TODO 失败根因 --> |"
        )
    return "\n".join(rows)


def render_self_description_table(data: dict[str, Any], chart: dict[str, Any]) -> str:
    rows = [
        "| 供应商 | 除息日 | 每股金额 | 币种 | 可确定/6 |",
        "|---|---|---|---|---|",
    ]
    elements = ("ex_date", "amount", "currency")
    for provider, sd in sorted(data["self_description"].items()):
        name = _provider_name(chart, provider)
        total = sd.get("total", 0)
        denom = sd.get("denominator", 6)
        cells = []
        for e in elements:
            value = sd.get(e)
            if value is None:
                cells.append("—")
            else:
                p, t = value.split("/")
                cells.append("能" if p == t else ("波动" if p != "0" else "不能"))
        rows.append(f"| {name} | {' | '.join(cells)} | {total}/{denom} |")
    return "\n".join(rows)


def render_interpretation_summary(data: dict[str, Any], chart: dict[str, Any]) -> str:
    interp = data.get("interpretation", {})
    if not interp:
        return "<!-- TODO 出参解读（无证据数据） -->"
    parts = []
    for question, info in sorted(interp.items()):
        parts.append(f"{question} {info['passed']}/{info['total']}")
    return "出参解读：<!-- TODO 完整解读 -->（" + "；".join(parts) + "）"


def aggregate_records(
    records: list[dict[str, Any]],
    *,
    provider_key: str,
    passed_key: str = "passed",
) -> dict[str, dict[str, Any]]:
    """Aggregate probe records per provider into pass/total counts."""
    per: dict[str, dict[str, int]] = {}
    for record in records:
        provider = record.get(provider_key)
        if not provider:
            continue
        agg = per.setdefault(provider, {"passed": 0, "total": 0})
        agg["total"] += 1
        if record.get(passed_key):
            agg["passed"] += 1
    return per


def load_probe_data(args: argparse.Namespace) -> dict[str, Any]:
    """Load and aggregate the newest probe batch per provider."""
    direct = _latest_batch(load_jsonl(args.direct))
    param = _latest_batch(load_jsonl(args.param))
    recovery = _latest_batch(load_jsonl(args.recovery))
    interp = _latest_batch(load_jsonl(args.interpret))
    selfdesc = _latest_batch(load_jsonl(args.self_description))

    # Direct Test: only passed positive calls count toward latency/cost;
    # negative controls and failed cells are excluded from both metrics.
    dt: dict[str, dict[str, Any]] = {}
    for provider in _provider_ids(direct):
        cells = [r for r in direct if r.get("provider_id") == provider]
        passed_cells = [r for r in cells if r.get("state") == "passed"]
        passed = len(passed_cells)
        lat = [r["latency_ms"] for r in passed_cells if r.get("latency_ms") is not None]
        cost = [
            value
            for r in passed_cells
            if isinstance((value := r.get("cost_credits")), (int, float)) and value > 0
        ]
        dt[provider] = {
            "passed": passed,
            "total": len(cells),
            "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None,
            "success_call_credits": round(sum(cost) / len(cost), 2) if cost else None,
        }

    sd: dict[str, dict[str, Any]] = {}
    for provider in _provider_ids(selfdesc):
        cells = [r for r in selfdesc if r.get("provider_id") == provider]
        determined = sum(1 for r in cells if r.get("determined"))
        by_element: dict[str, str] = {}
        for element in {
            value for r in cells if isinstance((value := r.get("element")), str)
        }:
            sub = [r for r in cells if r.get("element") == element]
            p = sum(1 for r in sub if r.get("determined"))
            by_element[element] = f"{p}/{len(sub)}"
        sd[provider] = {
            "total": determined,
            "denominator": len(cells),
            **by_element,
        }

    return {
        "direct_test": dt,
        "param_fill": aggregate_records(param, provider_key="provider_id"),
        "error_recovery": aggregate_records(recovery, provider_key="provider_id"),
        "interpretation": aggregate_records(interp, provider_key="question_id"),
        "self_description": sd,
    }


def render_article(
    data: dict[str, Any], chart: dict[str, Any], guide_label: str, edition: str
) -> str:
    label = guide_label or chart.get("guide_label", "对比")
    # guide_label may already carry the API suffix; avoid "分红数据 API API".
    if label.endswith("API"):
        label = label[: -len("API")].rstrip()
    edition_date = edition or chart.get("edition_date", "2026-08-10")
    observation = chart.get("observation_date", edition_date)
    market_universe = ", ".join(str(item) for item in chart.get("market_universe", []))
    supplier_count = len(chart.get("suppliers", []))

    main_table = render_main_table(data, chart)
    param_table = render_param_fill_table(data, chart)
    recovery_table = render_recovery_table(data, chart)
    sd_table = render_self_description_table(data, chart)
    interp = render_interpretation_summary(data, chart)

    return f"""# {edition_date} {label} API 对比

## 快速结论

- <!-- TODO 直接回答：A 股/全球/低成本 各选谁 + 一句话理由 -->
- <!-- TODO AI 友好度一句话概览（入参/自愈/自解释差异） -->
- <!-- TODO 选型原则 -->

> 本文结论来自本平台 {edition_date} 真实调用实测（Direct Test 2 轮 + AI 友好度四维度，固定模型）。**我们公布证据，不公布排名**——不合成综合评分，每个维度独立呈现。完整方法论见[我们的方法论](_shared/benchmark-methodology.md)。

## 哪个 {label} API 能让 AI 自动取到答案？

<!-- TODO 铰链问题 + 结论卡表（场景 | 首选 | 为什么 | 注意） -->

## {supplier_count} 家 {label} API 对比总表

{edition_date} 经 QVeris 网关真实执行，固定用例（正向 + 负向控制）每单元 2 轮。单次费用为成功调用价，负向控制不计费。观察日期 {observation}。

{main_table}

（AI 落参/自愈 = 通过轮数/总轮数；自解释 = 仅凭响应能确定的字段数/样本数，测试日期 {edition_date}。）

![{label} API 延迟与单次费用](capability-seo/charts/chart-latency-cost.png)

<!-- TODO 综合判断一段 -->

## 按使用场景选择

### <!-- TODO 场景一（如 A 股） -->
<!-- TODO 场景推荐 + 证据支撑 -->

### <!-- TODO 场景二（如全球） -->
<!-- TODO 场景推荐 + 证据支撑 -->

## 供应商深度解析

{param_table}

{recovery_table}

{sd_table}

{interp}

<!-- TODO 每家供应商一段深度解析 -->
<!-- TODO 可下钻观测卡 2-3 张 -->

## {label} API 的真实限制

<!-- TODO 5 条生产环境真实限制（除息日口径/金额口径/币种/错误信号/负向） -->

## 市场覆盖

覆盖判定以工具 namespace 覆盖为准（claimed_namespaces − SV 探测失败的 unsupported_namespaces，经 SNS 注册表解析）。以下为 claimed 口径，namespace 探测补跑后可能收缩。

<!-- TODO 市场覆盖矩阵表 + 图 -->

## 怎么选（决策清单）

1. <!-- TODO 先定市场 -->
2. <!-- TODO 确认字段 -->
3. <!-- TODO Agent 自动调用 -->
4. <!-- TODO 冒烟测试 -->

## {label} API Python 示例

<!-- TODO 一段可运行调用示例 -->

## 常见问题

**<!-- TODO 问题 1 -->** <!-- TODO 回答 -->
**<!-- TODO 问题 2 -->** <!-- TODO 回答 -->

## 局限与时效

- 本文为 {edition_date} 单次执行快照：Direct Test 固定用例 × 2 轮，非全量场景认证；延迟/费用为经 QVeris 网关平均值，不代表供应商直连或 p95，会随套餐、路由与市场状况变化。
- AI 友好度基于固定模型单次测试，模型对同一失败响应的重试参数存在轮间波动，判定以逐轮真实执行结果为准。
- 响应自解释以各家一个冻结响应为样本；出参解读为通用样本，各家逐测待补齐。
- 市场覆盖为 claimed 口径，namespace 探测部分缺失，补跑后以结果为准。
- 市场覆盖 universe：{market_universe}。

## 在集成前，先验证这 {supplier_count} 家

每个数字背后是可复现的固定用例。想深入核验某家供应商的接口表现，可在 QVeris 中直接检查：

<!-- TODO CTA 链接（2 家重点供应商） -->

完整方法论、判定规则与冻结样本见 [我们的方法论](_shared/benchmark-methodology.md) 和 [QVeris Capability Benchmarks](https://github.com/QVerisAI/qveris-capability-benchmarks)。

## 更正与复测

我们只发布可复现的实测结论，并保留全部固定输入用例。若你是供应商并认为某行不准确，请提交带可复现用例的事实更正；入选与排名均不可购买。每次出新版，我们以同一套固定用例重跑，2–4 小时刷新一轮。

相关指南：

<!-- TODO 相关指南链接 -->
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart-data", type=Path, required=True)
    parser.add_argument(
        "--direct", type=Path, default=Path("evidence/private/cap-direct-test.jsonl")
    )
    parser.add_argument(
        "--param", type=Path, default=Path("evidence/private/agent-param-fill.jsonl")
    )
    parser.add_argument(
        "--recovery",
        type=Path,
        default=Path("evidence/private/agent-error-recovery.jsonl"),
    )
    parser.add_argument(
        "--interpret",
        type=Path,
        default=Path("evidence/private/agent-response-interpretation.jsonl"),
    )
    parser.add_argument(
        "--self-description",
        type=Path,
        default=Path("evidence/private/agent-response-self-description.jsonl"),
    )
    parser.add_argument("--guide-label", default="")
    parser.add_argument("--edition", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    inputs: list[tuple[str, Path]] = [
        ("--chart-data", args.chart_data),
        ("--direct", args.direct),
        ("--param", args.param),
        ("--recovery", args.recovery),
        ("--interpret", args.interpret),
        ("--self-description", args.self_description),
    ]
    for flag, path in inputs:
        if not path.exists():
            print(
                f"错误: {flag} 指向的文件不存在: {path}（请先运行 probe runner 生成 evidence）",
                file=sys.stderr,
            )
            return 1

    chart = load_chart_data(args.chart_data)
    data = load_probe_data(args)
    _warn_provider_mismatch(chart, data)
    article = render_article(data, chart, args.guide_label, args.edition)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(article, encoding="utf-8")
    print(f"written: {args.output} ({len(article.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
