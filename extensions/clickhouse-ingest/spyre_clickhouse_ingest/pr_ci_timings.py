# Copyright 2026 The Torch-Spyre Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Write one PR-triggered orchestrator run's timeline (a JSON batch) into pr_ci_timings."""

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .identity import DerivedId
from .schema import PR_TEST_STATE_VALUES, PrCiTimings

# The keys each batch section may carry; an unknown key is refused so a typo cannot read as NULL.
BATCH_KEYS = {
    "run": {
        "run_key",
        "trigger_pr",
        "trigger_source",
        "preset",
        "build_url",
        "verdict",
        "result",
        "pickup_path",
        "comment_at",
        "picked_up_at",
        "scheduled_at",
        "started_at",
        "queued_at",
        "running_at",
        "ended_at",
        "props",
    },
    "nodes": {
        "component",
        "artifact_name",
        "arch",
        "id12",
        "kind",
        "state",
        "url",
        "agent",
        "queued_at",
        "started_at",
        "ended_at",
    },
    "tests": {
        "component",
        "artifact_name",
        "arch",
        "id12",
        "kind",
        "modes",
        "state",
        "result",
        "url",
        "dispatched_at",
        "started_at",
        "ended_at",
        "gha",
    },
    "gha": {
        "mode",
        "run_url",
        "conclusion",
        "jobs",
        "deploy_started_at",
        "deploy_ended_at",
        "dispatched_at",
        "created_at",
        "first_job_started_at",
        "completed_at",
    },
}

# A stateless leg's Jenkins result; anything unlisted (ABORTED, NOT_BUILT) gave no test signal.
RESULT_STATES = {"success": "passed", "failure": "failed", "unstable": "failed"}
# Worst first: a failed workflow is the change's verdict, an error says nothing about it.
STATE_ORDER = ("failed", "error", "passed")


def check_batch(batch: Mapping[str, Any]) -> None:
    """Raise ValueError naming every unknown section or key in `batch`."""
    bad = [f"section {k!r}" for k in batch if k not in ("run", "nodes", "tests")]
    bad += [f"run.{k}" for k in batch.get("run") or {} if k not in BATCH_KEYS["run"]]
    for section in ("nodes", "tests"):
        for i, e in enumerate(batch.get(section) or []):
            bad += [f"{section}[{i}].{k}" for k in e if k not in BATCH_KEYS[section]]
    for i, t in enumerate(batch.get("tests") or []):
        for j, g in enumerate(t.get("gha") or []):
            bad += [f"tests[{i}].gha[{j}].{k}" for k in g if k not in BATCH_KEYS["gha"]]
    if not (batch.get("run") or {}).get("run_key"):
        bad.append("run.run_key (missing)")
    if bad:
        raise ValueError("bad batch key(s): " + ", ".join(bad))


def ts(value: Any) -> datetime | None:
    """Epoch milliseconds or ISO-8601 as an aware UTC datetime; None when unknown."""
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, (int, float)) or str(value).strip().isdigit():
        ms = int(value)
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms > 0 else None
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    return (
        parsed.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None
        else parsed.astimezone(timezone.utc)
    )


def span_ms(start: datetime | None, end: datetime | None) -> int | None:
    """Milliseconds from start to end, None when either is unknown, 0 when end is earlier."""
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def _first(values: Iterable[datetime | None]) -> datetime | None:
    known = [v for v in values if v is not None]
    return min(known) if known else None


def _last(values: Iterable[datetime | None]) -> datetime | None:
    known = [v for v in values if v is not None]
    return max(known) if known else None


def split_trigger_pr(trigger_pr: str) -> tuple[str, int]:
    """'<host>/<owner>/<repo>#<n>' -> (repo, n); ('', 0) when it is not that shape."""
    path, _, num = (trigger_pr or "").strip().rpartition("#")
    repo = path.rstrip("/").rsplit("/", 1)[-1]
    return (repo, int(num)) if path and num.isdigit() else ("", 0)


def _key(entry: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("component") or ""),
        str(entry.get("artifact_name") or ""),
        DerivedId.arch(entry.get("arch") or ""),
    )


def leg_state(entry: Mapping[str, Any]) -> str:
    """The leg's state, else its Jenkins result mapped onto the same vocabulary."""
    state = str(entry.get("state") or "").strip().lower()
    if state in PR_TEST_STATE_VALUES and state:
        return state
    result = str(entry.get("result") or "").strip().lower()
    return RESULT_STATES.get(result, "error") if result else ""


def _worst(states: Iterable[str]) -> str:
    present = set(states)
    return next((s for s in STATE_ORDER if s in present), "")


def _conclusion(runs: list[Mapping[str, Any]]) -> str:
    """The first conclusion that is not success, else success; unknowns are skipped."""
    known = [str(g.get("conclusion") or "").lower().strip("_") for g in runs]
    known = [v for v in known if v]
    return next((v for v in known if v != "success"), "success" if known else "")


def _run_fields(run: Mapping[str, Any]) -> dict[str, Any]:
    t = {
        k: ts(run.get(k))
        for k in (
            "comment_at",
            "picked_up_at",
            "scheduled_at",
            "started_at",
            "queued_at",
            "running_at",
            "ended_at",
        )
    }
    trigger_pr = str(run.get("trigger_pr") or "")
    repo, pr_number = split_trigger_pr(trigger_pr)
    return {
        "run_key": str(run["run_key"]),
        "trigger_pr": trigger_pr,
        "repo": repo,
        "pr_number": pr_number,
        "trigger_source": str(run.get("trigger_source") or ""),
        "preset": str(run.get("preset") or ""),
        "build_url": str(run.get("build_url") or ""),
        "verdict": str(run.get("verdict") or "").lower(),
        "run_result": str(run.get("result") or "").lower(),
        "pickup_path": str(run.get("pickup_path") or ""),
        "comment_at": t["comment_at"],
        "picked_up_at": t["picked_up_at"],
        "run_scheduled_at": t["scheduled_at"],
        "run_started_at": t["started_at"],
        "queued_at": t["queued_at"],
        "running_at": t["running_at"],
        "run_ended_at": t["ended_at"],
        "comment_to_pickup_ms": span_ms(t["comment_at"], t["picked_up_at"]),
        "comment_to_queued_ms": span_ms(t["comment_at"], t["queued_at"]),
        "queued_to_running_ms": span_ms(t["queued_at"], t["running_at"]),
        "comment_to_end_ms": span_ms(t["comment_at"], t["ended_at"]),
        "run_ms": span_ms(t["started_at"], t["ended_at"]),
        "props": {str(k): str(v) for k, v in (run.get("props") or {}).items()},
    }


def _build_fields(node: Mapping[str, Any] | None) -> dict[str, Any]:
    node = node or {}
    queued, started, ended = (
        ts(node.get(k)) for k in ("queued_at", "started_at", "ended_at")
    )
    return {
        "build_state": str(node.get("state") or "").lower(),
        "build_job_url": str(node.get("url") or ""),
        "build_agent": str(node.get("agent") or ""),
        "build_queued_at": queued,
        "build_started_at": started,
        "build_ended_at": ended,
        "build_queue_ms": span_ms(queued, started),
        "build_ms": span_ms(started, ended),
    }


def _test_fields(tests: list[Mapping[str, Any]]) -> dict[str, Any]:
    runs = [g for t in tests for g in (t.get("gha") or [])]
    modes = sorted(
        {
            m.strip()
            for t in tests
            for m in str(t.get("modes") or "").split(",")
            if m.strip()
        }
    )
    dispatched = _first(ts(t.get("dispatched_at")) for t in tests)
    started = _first(ts(t.get("started_at")) for t in tests)
    ended = _last(ts(t.get("ended_at")) for t in tests)
    # A workflow starts at its dispatch, or its creation when the dispatcher recorded none.
    run_start = [ts(g.get("dispatched_at")) or ts(g.get("created_at")) for g in runs]
    gha_dispatched = _first(run_start)
    gha_completed = _last(ts(g.get("completed_at")) for g in runs)
    deploys = [
        span_ms(ts(g.get("deploy_started_at")), ts(g.get("deploy_ended_at")))
        for g in runs
    ]
    waits = [
        span_ms(start, ts(g.get("first_job_started_at")))
        for start, g in zip(run_start, runs)
    ]
    deploys = [d for d in deploys if d is not None]
    waits = [w for w in waits if w is not None]
    return {
        "test_modes": modes,
        "test_state": _worst(leg_state(t) for t in tests),
        "test_dispatched_at": dispatched,
        "test_leg_started_at": started,
        "runner_deploy_started_at": _first(
            ts(g.get("deploy_started_at")) for g in runs
        ),
        "runner_deploy_ended_at": _last(ts(g.get("deploy_ended_at")) for g in runs),
        "gha_dispatched_at": gha_dispatched,
        "gha_created_at": _first(ts(g.get("created_at")) for g in runs),
        "gha_first_job_started_at": _first(
            ts(g.get("first_job_started_at")) for g in runs
        ),
        "gha_completed_at": gha_completed,
        "test_leg_ended_at": ended,
        "gha_runs": len(runs),
        "gha_jobs": sum(int(g.get("jobs") or 0) for g in runs),
        "gha_conclusion": _conclusion(runs),
        "gha_run_urls": list(
            dict.fromkeys(str(g["run_url"]) for g in runs if g.get("run_url"))
        ),
        "test_leg_queue_ms": span_ms(dispatched, started),
        "runner_deploy_ms": sum(deploys) if deploys else None,
        "gha_queue_ms": max(waits) if waits else None,
        "gha_e2e_ms": span_ms(gha_dispatched, gha_completed),
        "gha_to_leg_end_ms": span_ms(gha_completed, ended),
        "test_leg_ms": span_ms(dispatched, ended),
    }


def build_rows(
    batch: Mapping[str, Any], now: datetime | None = None
) -> list[dict[str, Any]]:
    """The pr_ci_timings rows of one batch, one per (component, artifact_name, arch)."""
    check_batch(batch)
    run = _run_fields(batch["run"])
    updated_at = now or datetime.now(timezone.utc)
    nodes: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for n in batch.get("nodes") or []:
        # A node built twice in one run (a retried lane) keeps its later attempt.
        nodes[_key(n)] = n
    tests: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for t in batch.get("tests") or []:
        tests.setdefault(_key(t), []).append(t)

    rows = []
    for key in sorted(set(nodes) | set(tests)):
        component, artifact_name, arch = key
        if not component:
            continue
        node = nodes.get(key)
        legs = tests.get(key, [])
        first = node or legs[0]
        rows.append(
            {
                **run,
                "updated_at": updated_at,
                "component": component,
                "artifact_name": artifact_name,
                "arch": arch,
                "id12": str(first.get("id12") or ""),
                "kind": str(first.get("kind") or ""),
                "is_trigger_component": bool(run["repo"]) and component == run["repo"],
                **_build_fields(node),
                **_test_fields(legs),
            }
        )
    return rows


def write_batch(client, db: str, batch: Mapping[str, Any]) -> int:
    """Insert every row of `batch`; returns how many were written."""
    return PrCiTimings.insert(client, build_rows(batch), db=db)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", default="", help="default: $CLICKHOUSE_DB_V2")
    sub = parser.add_subparsers(dest="cmd", required=True)
    wr = sub.add_parser("write", help="one run's timeline batch (JSON)")
    wr.add_argument("batch", type=Path)
    wr.add_argument(
        "--dry-run", action="store_true", help="print the rows instead of writing them"
    )
    args = parser.parse_args(argv)

    batch = json.loads(args.batch.read_text())
    if args.dry_run:
        for row in build_rows(batch):
            # The same validation an insert applies, so a dry run fails where a write would.
            PrCiTimings.row(row)
            print(json.dumps(row, default=str, sort_keys=True))
        return

    from .client import ClickHouse, ClickHouseEnv

    db = args.database or ClickHouseEnv.target_database()
    if not db:
        sys.exit("[error] no database: pass --database or set CLICKHOUSE_DB_V2")
    client = ClickHouse.connect(database=db)
    done = write_batch(client, db, batch)
    print(f"[info] {db}: {done} pr_ci_timings row(s) for {batch['run']['run_key']}")


if __name__ == "__main__":
    main()
