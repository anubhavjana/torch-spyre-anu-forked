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

"""Pins the per-tag latest-outcome view."""

import regex as re

from spyre_clickhouse_ingest.apply_schema import SCHEMA_DIR, SchemaApplier


def _statuses():
    sql = (SCHEMA_DIR / "10-functional-tests.sql").read_text()
    listed = re.search(r"chk_status CHECK status IN\s*\(([^)]*)\)", sql).group(1)
    return set(re.findall(r"'([^']+)'", listed))


def test_view_is_declared_and_ranks_every_status():
    path = SCHEMA_DIR / "52-cross-views.sql"
    views = {
        o.name: o
        for o in SchemaApplier.objects(path, path.read_text())
        if o.kind == "view"
    }
    sql = views["v_tag_case_latest"].sql
    ranked = re.search(r"indexOf\(\[([^\]]*)\]", sql).group(1)
    assert set(re.findall(r"'([^']+)'", ranked)) == _statuses()
