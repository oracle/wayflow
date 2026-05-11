#!/usr/bin/env bash

# Copyright © 2025, 2026 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

set -euo pipefail

# Generate the Pydantic models for the OpenAI Responses API spec.

# SHA for the upstream spec when it reported info.version 2.3.0.
spec_sha256="2de8031d85add4117952fc327644b9e6dfc0453d9367c03c10d2bf217d0a2a5d"
spec_path="data/openapi.documented.yml"

# Run from this script folder and make sure the data folder exists.
cd "$(dirname "$0")"
mkdir -p data

# Download the spec in a tmp file and check its SHA.
tmp_spec="$(mktemp "${TMPDIR:-/tmp}/openapi.documented.XXXXXX.yml")"
trap 'rm -f "$tmp_spec"' EXIT

curl -fsSL --proto '=https' "https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml" -o "$tmp_spec"
python verify_openapi_spec.py "$tmp_spec" "$spec_sha256"

# If everything is ok, save the approved spec file
mv "$tmp_spec" "$spec_path"

# Filter only the models needed for the APIs we want to support (responses)
python generate_models.py --spec "$spec_path"

# Build the Pydantic models.
python generate_pydantic_models.py --spec "$spec_path"

# Copy the models in src/wayflowcore/agentserver/models/openairesponsespydanticmodels.py
# and run formatting with git hooks
