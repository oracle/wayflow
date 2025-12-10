# Copyright © 2025 Oracle and/or its affiliates.
#
# This software is under the Apache License 2.0
# (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0) or Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl), at your option.

# THIS FILE IS USED TO GENERATE THE PYDANTIC MODELS FOR THE OPENAI RESPONSES PEN API SPEC

#
mkdir -p data

# 1. get the latest version of the open API spec
wget -N -P data https://app.stainless.com/api/spec/documented/openai/openapi.documented.yml

# 2. filter only the models needed for the APIs we want to support (responses)
python generate_models.py

# 3. generate the pydantic models for these models
python generate_pydantic_models.py

# 4. copy the models in src/wayflowcore/agentserver/models/openairesponsespydanticmodels.py
# and run formatting with git hooks
