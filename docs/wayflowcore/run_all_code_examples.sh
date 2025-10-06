#!/bin/bash
#
# Copyright (C) 2024, 2025 Oracle and/or its affiliates.
#
# This software is under the Universal Permissive License
# (UPL) 1.0 (LICENSE-UPL or https://oss.oracle.com/licenses/upl) or Apache License
# 2.0 (LICENSE-APACHE or http://www.apache.org/licenses/LICENSE-2.0), at your option.

set -e # we should crash this bash script as soon as a python script crashes

find source/core/code_examples -type f -name '*.py' | while read file; do
  echo "Running code example: $file"
  python $file
done
