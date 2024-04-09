"""Module to convert voluptuous schemas to dictionaries."""

from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from typing import Any

import voluptuous as vol


TYPES_MAP = {
    int: "integer",
    str: "string",
    float: "number",
    bool: "boolean",
}

UNSUPPORTED = object()


def convert(schema: Any, *, custom_serializer: Callable | None = None) -> dict:
    """Convert a voluptuous schema to a OpenAPI Schema object."""
    # pylint: disable=too-many-return-statements,too-many-branches
    additional_properties = None
    if isinstance(schema, vol.Schema):
        if schema.extra == vol.ALLOW_EXTRA:
            additional_properties = True
        schema = schema.schema

    if custom_serializer:
        val = custom_serializer(schema)
        if val is not UNSUPPORTED:
            return val

    if isinstance(schema, Mapping):
        properties = {}
        required = []

        # Unfold vol.Any in keys
        if vol.Any in [type(k) for k in schema.keys()]:
            pschema = {}
            for key, value in schema.items():
                if isinstance(key, vol.Any):
                    description = key.msg
                    if not description:
                        description = (
                            f"At least one of {key.validators} must be provided"
                        )
                    for val in key.validators:
                        pschema[vol.Optional(val, description=description)] = value
                else:
                    pschema[key] = value
            schema = pschema

        for key, value in schema.items():
            description = None
            if isinstance(key, vol.Marker):
                pkey = key.schema
                description = key.description
            else:
                pkey = key

            pval = convert(value, custom_serializer=custom_serializer)
            if description:
                pval["description"] = key.description

            if isinstance(key, (vol.Required, vol.Optional)):
                if key.default is not vol.UNDEFINED:
                    pval["default"] = key.default()

            pkey = str(pkey)
            properties[pkey] = pval

            if isinstance(key, vol.Required):
                required.append(pkey)

        val = {"type": "object", "properties": properties, "required": required}
        if additional_properties:
            val["additionalProperties"] = additional_properties
        return val

    if isinstance(schema, vol.All):
        val = {}
        fallback = False
        allOf = []
        for validator in schema.validators:
            v = convert(validator, custom_serializer=custom_serializer)
            if not v:
                continue
            if v.keys() & val.keys():
                # Some of the keys are intersecting - fallback to allOf
                fallback = True
            allOf.append(v)
            if not fallback:
                val.update(v)
        if fallback:
            return {"allOf": allOf}
        return val

    if isinstance(schema, (vol.Clamp, vol.Range)):
        val = {}
        if schema.min is not None:
            if isinstance(schema, vol.Clamp) or schema.min_included:
                val["minimum"] = schema.min
            else:
                val["exclusiveMinimum"] = schema.min
        if schema.max is not None:
            if isinstance(schema, vol.Clamp) or schema.max_included:
                val["maximum"] = schema.max
            else:
                val["exclusiveMaximum"] = schema.max
        return val

    if isinstance(schema, vol.Length):
        val = {}
        if schema.min is not None:
            val["minLength"] = schema.min
        if schema.max is not None:
            val["maxLength"] = schema.max
        return val

    if isinstance(schema, vol.Datetime):
        return {
            "type": "string",
            "format": "date-time",
        }

    if isinstance(schema, vol.Match):
        return {"pattern": schema.pattern.pattern}

    if isinstance(schema, vol.In):
        if isinstance(schema.container, Mapping):
            return {"enum": list(schema.container.keys())}
        return {"enum": schema.container}

    if schema in (vol.Lower, vol.Upper, vol.Capitalize, vol.Title, vol.Strip):
        return {
            "format": schema.__name__.lower(),
        }

    if schema in (vol.Email, vol.Url, vol.FqdnUrl):
        return {
            "format": schema.__name__.lower(),
        }

    if isinstance(schema, vol.Any):
        # vol.Maybe
        if len(schema.validators) == 2 and schema.validators[0] is None:
            result = convert(schema.validators[1], custom_serializer=custom_serializer)
            result["nullable"] = True
            return result

        return {
            "anyOf": [
                convert(val, custom_serializer=custom_serializer)
                for val in schema.validators
            ]
        }

    if isinstance(schema, vol.Coerce):
        schema = schema.type

    if isinstance(schema, (str, int, float, bool)) or schema is None:
        return {"enum": [schema]}

    if isinstance(schema, Sequence):
        if len(schema) == 1:
            return {
                "type": "array",
                "items": convert(schema[0], custom_serializer=custom_serializer),
            }
        return {
            "type": "array",
            "items": [
                convert(s, custom_serializer=custom_serializer) for s in schema.items()
            ],
        }

    if schema in TYPES_MAP:
        return {"type": TYPES_MAP[schema]}

    if isinstance(schema, type) and issubclass(schema, Enum):
        return {"enum": [item.value for item in schema]}

    raise ValueError("Unable to convert schema: {}".format(schema))