#!/usr/bin/env python3
"""Scope the vendored OpenAPI spec to what this SDK actually exposes.

The SDK wraps every modality in the spec — image, audio, video, document,
fact-checking — so no paths are dropped. What IS dropped is detail the SDK does not
surface: the per-provider video breakdown, which would name the detection backend in
generated `.d.ts` / models. Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

SPEC = Path(__file__).with_name("openapi.yaml")


def _strip_keys(node: object, names: set[str]) -> None:
    """Recursively delete every dict entry whose key is in ``names``."""
    if isinstance(node, dict):
        for key in list(node):
            if key in names:
                del node[key]
            else:
                _strip_keys(node[key], names)
    elif isinstance(node, list):
        for item in node:
            _strip_keys(item, names)

# Paths whose route contains any of these substrings are removed. The SDK wraps every
# detection modality the spec publishes; tenant data export is an admin-granted,
# privileged surface (its own scope) that the SDK deliberately does not wrap.
DROP_PATH_SUBSTRINGS: tuple[str, ...] = ("/api/app/data-export",)
# Exact component schemas to remove. The SDK does not surface per-provider
# breakdown detail, so this shape is dropped from the generated types.
DROP_SCHEMA_NAMES = {
    "VideoProvider",
    # Only the dropped data-export paths reference these.
    "DataExportRequest",
    "DataExportJob",
    "PagedDataExportJobs",
    "DataExportActivity",
    "PagedDataExportActivity",
    "DataExportDownloadToken",
}
# Object properties stripped wherever they appear (schema definitions and examples),
# tied to the removed schemas above so nothing dangles a reference to them.
DROP_PROPERTY_NAMES = {"providers"}
# Tags removed from the top-level tag list.
DROP_TAGS: set[str] = {"Data Export"}


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text())

    paths = spec.get("paths", {})
    for route in list(paths):
        if any(sub in route for sub in DROP_PATH_SUBSTRINGS):
            del paths[route]

    schemas = spec.get("components", {}).get("schemas", {})
    for name in list(schemas):
        if name in DROP_SCHEMA_NAMES:
            del schemas[name]

    # Strip the provider-breakdown property (schema definitions + example data)
    # everywhere it appears, so nothing references the removed shapes.
    _strip_keys(spec, DROP_PROPERTY_NAMES)

    # Reword any description that referenced a now-removed field by example.
    detailed = schemas.get("VideoResult", {}).get("properties", {}).get("hasDetailedReport")
    if isinstance(detailed, dict) and "description" in detailed:
        detailed["description"] = "True when a detailed report is available. False on basic plans."

    tags = spec.get("tags")
    if isinstance(tags, list):
        spec["tags"] = [t for t in tags if t.get("name") not in DROP_TAGS]

    # Prune response components no remaining path references, so no dead / stale-example
    # content lingers in the vendored spec.
    responses = spec.get("components", {}).get("responses", {})
    if responses:
        referenced = set(re.findall(r"#/components/responses/(\w+)", yaml.safe_dump(paths)))
        for name in list(responses):
            if name not in referenced:
                del responses[name]

    SPEC.write_text(
        yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=100000)
    )
    print(f"Scoped {SPEC.name} to the SDK's supported surface "
          f"({len(paths)} paths, {len(schemas)} schemas, {len(responses)} responses).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
