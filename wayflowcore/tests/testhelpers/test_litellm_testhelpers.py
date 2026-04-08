# Copyright © 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

import json

from tests.testhelpers import litellm_testhelpers


def test_litellm_testhelpers_read_vertex_project_id_from_inline_json(monkeypatch) -> None:
    monkeypatch.setenv("VERTEX_CREDENTIALS", json.dumps({"project_id": "project-id"}))

    assert litellm_testhelpers.get_vertex_credentials_dict() == {"project_id": "project-id"}
    assert litellm_testhelpers._get_vertex_project_id_from_service_account_credentials() == (
        "project-id"
    )
