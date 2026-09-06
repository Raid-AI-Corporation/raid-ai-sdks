#!/usr/bin/env bash
# Regenerate the Pydantic models from the vendored OpenAPI spec.
# Run after ../spec/openapi.yaml changes, then review + commit the result.
set -euo pipefail
cd "$(dirname "$0")/.."

datamodel-codegen \
  --input ../spec/openapi.yaml \
  --input-file-type openapi \
  --output src/raidxai/_generated/models.py \
  --output-model-type pydantic_v2.BaseModel \
  --use-annotated \
  --use-schema-description \
  --use-field-description \
  --field-constraints \
  --snake-case-field \
  --use-union-operator \
  --use-standard-collections \
  --target-python-version 3.10 \
  --formatters ruff-format

echo "Regenerated src/raidxai/_generated/models.py"
