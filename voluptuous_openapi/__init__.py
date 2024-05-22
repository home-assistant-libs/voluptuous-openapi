"""Module to convert voluptuous schemas to dictionaries."""

from collections.abc import Callable, Mapping, Sequence
from enum import Enum
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints
from types import NoneType, UnionType
from inspect import signature

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

    def ensure_default(value: dict[str:Any]):
        """Make sure that type is set."""
        if all(
            x not in value for x in ("type", "enum", "anyOf", "oneOf", "allOf", "not")
        ):
            value["type"] = "string"  # Type not determined, using default
        return value

    additional_properties = None
    if isinstance(schema, vol.Schema):
        if schema.extra == vol.ALLOW_EXTRA:
            additional_properties = True
        schema = schema.schema

    if custom_serializer:
        val = custom_serializer(schema)
        if val is not UNSUPPORTED:
            return val

    if isinstance(schema, vol.Object):
        schema = schema.schema
        if custom_serializer:
            val = custom_serializer(schema)
            if val is not UNSUPPORTED:
                return val

    if isinstance(schema, Mapping):
        properties = {}
        required = []

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

            pval = ensure_default(pval)

            if isinstance(pkey, type) and issubclass(pkey, str):
                if additional_properties is None:
                    additional_properties = pval
            elif isinstance(key, vol.Any):
                for val in key.validators:
                    if isinstance(val, vol.Marker):
                        if val.description:
                            properties[str(val.schema)] = pval.copy()
                            properties[str(val.schema)]["description"] = val.description
                        else:
                            properties[str(val)] = pval
                    else:
                        properties[str(val)] = pval
            else:
                properties[str(pkey)] = pval

            if isinstance(key, vol.Required):
                required.append(str(pkey))

        val = {"type": "object"}
        if properties or not additional_properties:
            val["properties"] = properties
            val["required"] = required
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
        return ensure_default(val)

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
        schema = schema.validators
        if None in schema or NoneType in schema:
            schema = [val for val in schema if val is not None and val is not NoneType]
            nullable = True
        else:
            nullable = False
        if len(schema) == 1:
            result = convert(schema[0], custom_serializer=custom_serializer)
        else:
            result = {
                "anyOf": [
                    convert(val, custom_serializer=custom_serializer) for val in schema
                ]
            }
        if nullable:
            result["nullable"] = True
        return result

    if isinstance(schema, vol.Coerce):
        schema = schema.type

    if isinstance(schema, (str, int, float, bool)) or schema is None:
        return {"enum": [schema]}

    if (
        get_origin(schema) is list
        or get_origin(schema) is set
        or get_origin(schema) is tuple
    ):
        schema = [get_args(schema)[0]]

    if isinstance(schema, Sequence):
        if len(schema) == 1:
            return {
                "type": "array",
                "items": ensure_default(
                    convert(schema[0], custom_serializer=custom_serializer)
                ),
            }
        return {
            "type": "array",
            "items": [
                ensure_default(convert(s, custom_serializer=custom_serializer))
                for s in schema.items()
            ],
        }

    if schema in TYPES_MAP:
        return {"type": TYPES_MAP[schema]}

    if get_origin(schema) is dict:
        if get_args(schema)[1] is Any or isinstance(get_args(schema)[1], TypeVar):
            schema = dict
        else:
            return convert({get_args(schema)[0]: get_args(schema)[1]})

    if isinstance(schema, type):
        if schema is dict:
            return {"type": "object", "additionalProperties": True}

        if schema is list or schema is set or schema is tuple:
            return {"type": "array", "items": ensure_default({})}

        if issubclass(schema, Enum):
            return {"enum": [item.value for item in schema]}
        elif schema is NoneType:
            return {"enum": [None]}

    if callable(schema):
        schema = get_type_hints(schema).get(
            list(signature(schema).parameters.keys())[0], Any
        )
        if schema is Any or isinstance(schema, TypeVar):
            return {}
        if isinstance(schema, UnionType) or get_origin(schema) is Union:
            schema = [t for t in get_args(schema) if not isinstance(t, TypeVar)]
            if len(schema) > 1:
                schema = vol.Any(*schema)
            elif len(schema) == 1 and schema[0] is not NoneType:
                schema = schema[0]
            else:
                return {}

        return convert(schema, custom_serializer=custom_serializer)

    raise ValueError("Unable to convert schema: {}".format(schema))
