"""JSON Schema loading and validation."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

from .errors import SuiteValidationError


def _schema_text(package: str, name: str) -> str:
    return resources.files(package).joinpath(name).read_text(encoding="utf-8")


def load_schema(name: str) -> dict[str, Any]:
    package = "config" if name == "verify.schema.json" else "schemas"
    schema = json.loads(_schema_text(package, name))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def validate_instance(instance: Any, schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(part) for part in first.absolute_path) or "<root>"
    raise SuiteValidationError(f"{schema_name}: {location}: {first.message}")


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise SuiteValidationError(f"{path}: top-level JSON value must be an object")
    return value
