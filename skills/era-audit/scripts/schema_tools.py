#!/usr/bin/env python3
"""Validate the JSON Schema subset used by era-audit artifacts."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def type_matches(value: Any, expected: str) -> bool:
    checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: (
            isinstance(item, (int, float)) and not isinstance(item, bool)
        ),
        "boolean": lambda item: isinstance(item, bool),
        "null": lambda item: item is None,
    }
    return expected in checks and checks[expected](value)


def resolve_ref(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"unsupported non-local schema reference: {reference}")
    value: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"unresolved schema reference: {reference}")
        value = value[part]
    if not isinstance(value, dict):
        raise ValueError(f"schema reference is not an object: {reference}")
    return value


def date_time_valid(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def validate_instance(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any] | None = None,
    path: str = "<root>",
) -> list[str]:
    root = root_schema or schema
    if "$ref" in schema:
        return validate_instance(
            value, resolve_ref(root, schema["$ref"]), root_schema=root, path=path
        )
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: value does not equal required constant")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not one of {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        options = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(type_matches(value, option) for option in options):
            errors.append(f"{path}: expected type {options!r}")
            return errors
    for branch in schema.get("allOf", []):
        errors.extend(validate_instance(value, branch, root_schema=root, path=path))
    condition = schema.get("if")
    if isinstance(condition, dict) and not validate_instance(
        value, condition, root_schema=root, path=path
    ):
        then = schema.get("then")
        if isinstance(then, dict):
            errors.extend(validate_instance(value, then, root_schema=root, path=path))
    if isinstance(value, dict):
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                errors.append(f"{path}: missing required property {name!r}")
        properties = schema.get("properties", {})
        for name, child in properties.items():
            if name in value:
                errors.extend(
                    validate_instance(
                        value[name], child, root_schema=root, path=f"{path}.{name}"
                    )
                )
        extras = set(value) - set(properties)
        additional = schema.get("additionalProperties", True)
        if additional is False:
            for name in sorted(extras):
                errors.append(f"{path}: unexpected property {name!r}")
        elif isinstance(additional, dict):
            for name in sorted(extras):
                errors.extend(
                    validate_instance(
                        value[name],
                        additional,
                        root_schema=root,
                        path=f"{path}.{name}",
                    )
                )
    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if isinstance(minimum_items, int) and len(value) < minimum_items:
            errors.append(f"{path}: requires at least {minimum_items} item(s)")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                errors.extend(
                    validate_instance(
                        item, items, root_schema=root, path=f"{path}[{index}]"
                    )
                )
    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(value) < minimum_length:
            errors.append(f"{path}: requires at least {minimum_length} character(s)")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{path}: does not match required pattern")
        if schema.get("format") == "date-time" and not date_time_valid(value):
            errors.append(f"{path}: is not an ISO date-time")
    minimum = schema.get("minimum")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum is not None
    ):
        if value < minimum:
            errors.append(f"{path}: is below minimum {minimum}")
    return errors
