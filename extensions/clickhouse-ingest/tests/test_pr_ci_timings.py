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

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from spyre_clickhouse_ingest import pr_ci_timings
from spyre_clickhouse_ingest.__main__ import main as cli
from spyre_clickhouse_ingest.schema import PrCiTimings, SchemaError

DDL = Path(__file__).resolve().parents[1] / "schema" / "48-pr-ci-timings.sql"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def _ms(iso: str) -> int:
    """Epoch ms of a UTC time, the form the Jenkins side sends."""
    return int(
        datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def _batch(**over):
    batch = {
        "run": {
            "run_key": "Spyre/orchestrator#4242",
            "trigger_pr": "github.ibm.com/ai-chip-toolchain/deeptools#4500",
            "trigger_source": "spyre-test",
            "preset": "trigger-pr-validation",
            "build_url": "https://jenkins/job/orchestrator/4242/",
            "verdict": "green",
            "result": "SUCCESS",
            "pickup_path": "webhook",
            "comment_at": "2026-10-08T10:00:00Z",
            "picked_up_at": _ms("2026-10-08T10:00:05"),
            "scheduled_at": _ms("2026-10-08T10:00:06"),
            "started_at": _ms("2026-10-08T10:00:10"),
            "queued_at": _ms("2026-10-08T10:00:30"),
            "running_at": _ms("2026-10-08T10:02:00"),
            "ended_at": _ms("2026-10-08T11:30:00"),
        },
        "nodes": [
            {
                "component": "deeptools",
                "artifact_name": "deeptools",
                "arch": "amd64",
                "id12": "aaaaaaaaaaaa",
                "kind": "rpm",
                "state": "built",
                "url": "https://jenkins/job/component-build/1/",
                "agent": "build-x86-1",
                "queued_at": _ms("2026-10-08T10:02:10"),
                "started_at": _ms("2026-10-08T10:02:40"),
                "ended_at": _ms("2026-10-08T10:20:40"),
            },
            {
                "component": "torch-spyre",
                "artifact_name": "torch-spyre-dev",
                "arch": "amd64",
                "id12": "bbbbbbbbbbbb",
                "kind": "image",
                "state": "built",
                "url": "https://jenkins/job/component-build/2/",
                "queued_at": _ms("2026-10-08T10:21:00"),
                "started_at": _ms("2026-10-08T10:21:00"),
                "ended_at": _ms("2026-10-08T10:41:00"),
            },
            {
                "component": "flex",
                "artifact_name": "flex",
                "arch": "amd64",
                "id12": "cccccccccccc",
                "kind": "rpm",
                "state": "reused",
            },
        ],
        "tests": [
            {
                "component": "torch-spyre",
                "artifact_name": "torch-spyre-dev",
                "arch": "x86_64",
                "modes": "integration",
                "state": "passed",
                "result": "SUCCESS",
                "url": "https://jenkins/job/component-build/3/",
                "dispatched_at": _ms("2026-10-08T10:41:05"),
                "started_at": _ms("2026-10-08T10:41:20"),
                "ended_at": _ms("2026-10-08T11:25:00"),
                "gha": [
                    {
                        "mode": "integration",
                        "run_url": "https://github.com/torch-spyre/torch-spyre/actions/runs/1",
                        "conclusion": "success",
                        "jobs": 4,
                        "deploy_started_at": _ms("2026-10-08T10:41:30"),
                        "deploy_ended_at": _ms("2026-10-08T10:42:30"),
                        "dispatched_at": "2026-10-08T10:42:40.500Z",
                        "created_at": "2026-10-08T10:42:41Z",
                        "first_job_started_at": "2026-10-08T10:46:40Z",
                        "completed_at": "2026-10-08T11:20:00Z",
                    }
                ],
            }
        ],
    }
    batch.update(over)
    return batch


def _by_component(rows):
    return {r["component"]: r for r in rows}


def test_model_columns_match_the_ddl_order():
    body = (
        DDL.read_text()
        .split("CREATE TABLE IF NOT EXISTS pr_ci_timings", 1)[1]
        .split("ENGINE", 1)[0]
    )
    cols = [
        line.split()[0]
        for line in body.splitlines()
        if line.startswith("    ")
        and not line.startswith("     ")
        and line.split()
        and not line.lstrip().startswith(("--", "(", ")"))
    ]
    assert list(PrCiTimings.columns) == [
        c for c in cols if c not in ("CONSTRAINT", "audit_uuid", "audit_timestamp")
    ]


def test_ddl_check_sets_match_the_model():
    ddl = DDL.read_text()
    assert "build_state IN ('built', 'failed', 'reused', '')" in ddl
    assert "test_state IN ('passed', 'failed', 'error', '')" in ddl


# ── one row per component artifact and arch, merged from builds and tests ──


def test_one_row_per_artifact_and_arch_merging_build_and_test():
    rows = pr_ci_timings.build_rows(_batch(), now=NOW)
    assert [(r["component"], r["arch"]) for r in rows] == [
        ("deeptools", "x86_64"),
        ("flex", "x86_64"),
        ("torch-spyre", "x86_64"),
    ]
    for r in rows:
        PrCiTimings.row(r)


def test_run_timeline_repeats_on_every_row():
    rows = pr_ci_timings.build_rows(_batch(), now=NOW)
    for r in rows:
        assert r["run_key"] == "Spyre/orchestrator#4242"
        assert (r["repo"], r["pr_number"]) == ("deeptools", 4500)
        assert r["comment_to_pickup_ms"] == 5_000
        assert r["comment_to_queued_ms"] == 30_000
        assert r["queued_to_running_ms"] == 90_000
        assert r["comment_to_end_ms"] == 90 * 60_000
        assert r["run_ms"] == 89 * 60_000 + 50_000
        assert r["verdict"] == "green" and r["run_result"] == "success"
        assert r["updated_at"] == NOW


def test_build_durations():
    r = _by_component(pr_ci_timings.build_rows(_batch(), now=NOW))["deeptools"]
    assert r["build_state"] == "built"
    assert r["build_queue_ms"] == 30_000
    assert r["build_ms"] == 18 * 60_000
    assert r["build_agent"] == "build-x86-1"
    assert r["test_modes"] == [] and r["test_state"] == ""
    assert r["gha_runs"] == 0 and r["gha_e2e_ms"] is None


def test_gha_leg_durations():
    r = _by_component(pr_ci_timings.build_rows(_batch(), now=NOW))["torch-spyre"]
    assert r["test_modes"] == ["integration"]
    assert r["test_state"] == "passed"
    assert r["test_leg_queue_ms"] == 15_000
    assert r["runner_deploy_ms"] == 60_000
    # Dispatch to the first job a runner picked up.
    assert r["gha_queue_ms"] == 3 * 60_000 + 59_500
    assert r["gha_e2e_ms"] == 37 * 60_000 + 19_500
    # Undeploy and the leg's own cleanup, after the last GHA job finished.
    assert r["gha_to_leg_end_ms"] == 5 * 60_000
    assert r["test_leg_ms"] == 43 * 60_000 + 55_000
    assert r["gha_runs"] == 1 and r["gha_jobs"] == 4
    assert r["gha_conclusion"] == "success"
    assert r["gha_run_urls"] == [
        "https://github.com/torch-spyre/torch-spyre/actions/runs/1"
    ]


def test_a_reused_node_has_no_build_time():
    r = _by_component(pr_ci_timings.build_rows(_batch(), now=NOW))["flex"]
    assert r["build_state"] == "reused"
    assert r["build_ms"] is None and r["build_queue_ms"] is None


def test_trigger_component_is_the_prs_own_repo():
    rows = _by_component(pr_ci_timings.build_rows(_batch(), now=NOW))
    assert rows["deeptools"]["is_trigger_component"] is True
    assert rows["torch-spyre"]["is_trigger_component"] is False


def test_a_test_without_a_build_still_gets_a_row():
    batch = _batch(nodes=[])
    (r,) = pr_ci_timings.build_rows(batch, now=NOW)
    assert r["component"] == "torch-spyre"
    assert r["build_state"] == "" and r["build_ms"] is None
    assert r["gha_e2e_ms"] is not None


def test_several_workflows_on_one_leg():
    batch = _batch()
    leg = batch["tests"][0]
    second = dict(
        leg["gha"][0],
        mode="smoke",
        run_url="https://github.com/torch-spyre/torch-spyre/actions/runs/2",
        conclusion="failure",
        jobs=2,
        deploy_started_at=_ms("2026-10-08T11:20:10"),
        deploy_ended_at=_ms("2026-10-08T11:20:40"),
        dispatched_at="2026-10-08T11:20:50Z",
        created_at="2026-10-08T11:20:51Z",
        first_job_started_at="2026-10-08T11:30:50Z",
        completed_at="2026-10-08T11:40:00Z",
    )
    leg["gha"].append(second)
    leg["ended_at"] = _ms("2026-10-08T11:41:00")
    r = _by_component(pr_ci_timings.build_rows(batch, now=NOW))["torch-spyre"]
    assert r["gha_runs"] == 2 and r["gha_jobs"] == 6
    # Sum of the deploys, not the span across the first workflow's tests.
    assert r["runner_deploy_ms"] == 90_000
    # The longest wait for a runner.
    assert r["gha_queue_ms"] == 10 * 60_000
    assert r["gha_e2e_ms"] == span(
        "2026-10-08T10:42:40.500+00:00", "2026-10-08T11:40:00+00:00"
    )
    assert r["gha_conclusion"] == "failure"
    assert len(r["gha_run_urls"]) == 2


@pytest.mark.parametrize(
    "conclusions, expect",
    [
        (["success", "success"], "success"),
        (["success", "failure"], "failure"),
        (["__never_started__"], "never_started"),
        ([None], ""),
        (["success", None], "success"),
        ([], ""),
    ],
)
def test_gha_conclusion(conclusions, expect):
    assert pr_ci_timings._conclusion([{"conclusion": c} for c in conclusions]) == expect


def span(a, b):
    return pr_ci_timings.span_ms(datetime.fromisoformat(a), datetime.fromisoformat(b))


def test_legs_of_one_artifact_roll_up_to_the_worst_state():
    batch = _batch()
    batch["tests"].append(
        dict(batch["tests"][0], modes="smoke", state="", result="FAILURE", gha=[])
    )
    r = _by_component(pr_ci_timings.build_rows(batch, now=NOW))["torch-spyre"]
    assert r["test_modes"] == ["integration", "smoke"]
    assert r["test_state"] == "failed"


@pytest.mark.parametrize(
    "entry, state",
    [
        ({"state": "passed"}, "passed"),
        ({"state": "ERROR"}, "error"),
        ({"state": "running", "result": "SUCCESS"}, "passed"),
        ({"result": "UNSTABLE"}, "failed"),
        ({"result": "ABORTED"}, "error"),
        ({}, ""),
    ],
)
def test_leg_state(entry, state):
    assert pr_ci_timings.leg_state(entry) == state


def test_the_gha_dispatch_falls_back_to_the_run_creation():
    batch = _batch()
    del batch["tests"][0]["gha"][0]["dispatched_at"]
    r = _by_component(pr_ci_timings.build_rows(batch, now=NOW))["torch-spyre"]
    assert r["gha_dispatched_at"] == r["gha_created_at"]
    assert r["gha_queue_ms"] == 3 * 60_000 + 59_000


# ── unknowns stay unknown ──


def test_a_run_with_no_comment_has_no_comment_durations():
    batch = _batch()
    batch["run"].update(comment_at="", picked_up_at=0, pickup_path="")
    r = pr_ci_timings.build_rows(batch, now=NOW)[0]
    assert r["comment_at"] is None
    assert r["comment_to_queued_ms"] is None
    assert r["comment_to_end_ms"] is None
    assert r["queued_to_running_ms"] == 90_000


@pytest.mark.parametrize("value", [None, "", 0, "0"])
def test_unknown_times(value):
    assert pr_ci_timings.ts(value) is None


def test_times_parse_from_millis_and_iso():
    expect = datetime(2026, 10, 8, 10, 0, 0, 250000, tzinfo=timezone.utc)
    assert pr_ci_timings.ts(_ms("2026-10-08T10:00:00") + 250) == expect
    assert pr_ci_timings.ts(str(_ms("2026-10-08T10:00:00") + 250)) == expect
    assert pr_ci_timings.ts("2026-10-08T10:00:00.250Z") == expect
    assert pr_ci_timings.ts("2026-10-08T12:00:00.250+02:00") == expect


def test_span_is_none_without_both_ends_and_never_negative():
    t = datetime(2026, 10, 8, tzinfo=timezone.utc)
    assert pr_ci_timings.span_ms(None, t) is None
    assert pr_ci_timings.span_ms(t, None) is None
    later = t.replace(second=1)
    assert pr_ci_timings.span_ms(later, t) == 0


@pytest.mark.parametrize(
    "trigger_pr, expect",
    [
        ("github.ibm.com/ai-chip-toolchain/flex#1457", ("flex", 1457)),
        ("github.com/torch-spyre/torch-spyre#3372", ("torch-spyre", 3372)),
        ("", ("", 0)),
        ("torch-spyre", ("", 0)),
    ],
)
def test_split_trigger_pr(trigger_pr, expect):
    assert pr_ci_timings.split_trigger_pr(trigger_pr) == expect


# ── the batch contract ──


def test_unknown_keys_are_refused():
    batch = _batch()
    batch["run"]["comment_time"] = "2026-10-08T10:00:00Z"
    batch["tests"][0]["gha"][0]["first_job_start"] = "x"
    with pytest.raises(ValueError) as e:
        pr_ci_timings.build_rows(batch)
    assert "run.comment_time" in str(e.value)
    assert "tests[0].gha[0].first_job_start" in str(e.value)


def test_a_batch_without_a_run_key_is_refused():
    batch = _batch()
    batch["run"]["run_key"] = ""
    with pytest.raises(ValueError, match="run.run_key"):
        pr_ci_timings.build_rows(batch)


def test_a_bad_build_state_fails_the_ddl_check():
    batch = _batch()
    batch["nodes"][0]["state"] = "published"
    rows = pr_ci_timings.build_rows(batch, now=NOW)
    with pytest.raises(SchemaError, match="build_state"):
        PrCiTimings.row(_by_component(rows)["deeptools"])


class FakeClient:
    def __init__(self):
        self.inserts = []

    def insert(self, table, rows, column_names=None, database=None):
        self.inserts.append((table, rows, column_names, database))


def test_write_batch_inserts_in_model_order_into_the_named_database():
    c = FakeClient()
    assert pr_ci_timings.write_batch(c, "spyre_v2", _batch()) == 3
    table, rows, cols, db = c.inserts[0]
    assert (table, db) == ("pr_ci_timings", "spyre_v2")
    assert cols == list(PrCiTimings.columns)
    assert len(rows) == 3 and all(len(r) == len(cols) for r in rows)


def test_cli_dry_run_prints_one_row_per_artifact(tmp_path, capsys):
    f = tmp_path / "batch.json"
    f.write_text(json.dumps(_batch()))
    cli(["pr-ci-timings", "write", str(f), "--dry-run"])
    lines = capsys.readouterr().out.splitlines()
    assert [json.loads(line)["component"] for line in lines] == [
        "deeptools",
        "flex",
        "torch-spyre",
    ]
