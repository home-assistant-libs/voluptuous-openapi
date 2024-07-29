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
        if all(x not in value for x in ("type", "anyOf", "oneOf", "allOf", "not")):
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

            if isinstance(key, vol.Any):
                for val in key.validators:
                    if isinstance(val, vol.Marker):
                        if val.description:
                            properties[str(val.schema)] = pval.copy()
                            properties[str(val.schema)]["description"] = val.description
                        else:
                            properties[str(val)] = pval
                    else:
                        properties[str(val)] = pval
            elif isinstance(pkey, str):
                properties[pkey] = pval
            else:
                if pval == {"type": "object", "additionalProperties": True}:
                    pval = True
                    additional_properties = None
                if additional_properties is None:
                    additional_properties = pval

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
            if (
                not v
                or v in allOf
                or v == {"type": "object", "additionalProperties": True}
            ):
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
            enum_values = list(schema.container.keys())
        else:
            enum_values = schema.container
        # Infer the enum type based on the type of the first value, but default
        # to a string as a fallback.
        if enum_values:
            enum_type = TYPES_MAP.get(type(enum_values[0]), "string")
        else:
            enum_type = "string"
        return {"type": enum_type, "enum": enum_values}

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
            anyOf = [
                convert(val, custom_serializer=custom_serializer) for val in schema
            ]
            if {"type": "object", "additionalProperties": True} in anyOf:
                result = {"type": "object", "additionalProperties": True}
            else:
                tmpAnyOf = []
                for item in anyOf:
                    if item in tmpAnyOf:  # Remove duplicated items
                        continue
                    tmpItem = item.copy()
                    if item.get(
                        "nullable"
                    ):  # Merge "nullable" property into an existing item
                        tmpItem.pop("nullable")
                        if tmpItem in tmpAnyOf:
                            tmpAnyOf[tmpAnyOf.index(tmpItem)]["nullable"] = True
                            continue
                    tmpItem["nullable"] = True
                    if tmpItem in tmpAnyOf:  # Ignore duplicated items that are nullable
                        continue
                    tmpAnyOf.append(item)

                if len(tmpAnyOf) == 1:
                    result = tmpAnyOf[0]
                else:
                    result = {"anyOf": tmpAnyOf}
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

    if schema is object:
        return {"type": "object", "additionalProperties": True}

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

        return ensure_default(convert(schema, custom_serializer=custom_serializer))

    raise ValueError("Unable to convert schema: {}".format(schema))
