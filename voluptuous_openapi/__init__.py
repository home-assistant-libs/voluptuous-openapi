"""Module to convert voluptuous schemas to dictionaries."""

from collections.abc import Callable, Mapping, Sequence
from inspect import signature
from enum import Enum, StrEnum
import itertools
import re
from typing import Any, TypeVar, Union, get_args, get_origin, get_type_hints
from types import NoneType, UnionType

import voluptuous as vol


TYPES_MAP = {
    int: "integer",
    str: "string",
    float: "number",
    bool: "boolean",
}
TYPES_MAP_REV = {v: k for k, v in TYPES_MAP.items()}

UNSUPPORTED = object()

# These are not supported when converting from OpenAPI to voluptuous
OPENAPI_UNSUPPORTED_KEYWORDS = {
    "allOf",
    "multipleOf",
    "uniqueItems",
}


class OpenApiVersion(StrEnum):
    """The OpenAPI version.

    This is used to change the behavior when converting schemas to OpenAPI.
    """

    V3 = "3.0"
    V3_1 = "3.1.0"


def convert(
    schema: Any,
    *,
    custom_serializer: Callable | None = None,
    openapi_version: OpenApiVersion = OpenApiVersion.V3,
) -> dict:
    """Convert a voluptuous schema to a OpenAPI Schema object."""
    # pylint: disable=too-many-return-statements,too-many-branches

    def convert_with_args(schema: Any) -> dict:
        """Convert schema for recusing and propagating arguments."""
        return convert(
            schema, custom_serializer=custom_serializer, openapi_version=openapi_version
        )

    def ensure_default(value: dict[str:Any]):
        """Make sure that type is set."""
        if all(x not in value for x in ("type", "anyOf", "oneOf", "allOf", "not")):
            if any(
                x in value
                for x in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
            ):
                value["type"] = "number"
            else:
                value["type"] = "string"
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
        any_of_constraint_groups: list[list[str]] = (
            []
        )  # List of lists, each containing candidate keys for a Required(Any(...))

        for key, value in schema.items():
            description = None
            if isinstance(key, vol.Marker):
                pkey = key.schema
                description = key.description
            else:
                pkey = key

            pval = convert_with_args(value)
            if description:
                pval["description"] = key.description

            if isinstance(key, vol.Required):
                if not isinstance(key.schema, vol.Any):
                    required.append(str(key.schema))
                if key.default is not vol.UNDEFINED:
                    pval["default"] = key.default()
            elif isinstance(key, vol.Optional):
                if key.default is not vol.UNDEFINED:
                    pval["default"] = key.default()

            pval = ensure_default(pval)

            if isinstance(pkey, vol.Any):
                # Handle Required(Any(...)) pattern for anyOf constraints
                if isinstance(key, vol.Required):
                    # Extract candidate keys and their descriptions from Any validator
                    candidate_items = []
                    for val_item in pkey.validators:
                        item_key = ""
                        item_desc = None
                        if isinstance(val_item, vol.Marker):
                            item_key = str(val_item.schema)
                            item_desc = val_item.description
                        else:
                            item_key = str(val_item)
                        candidate_items.append({"key": item_key, "desc": item_desc})

                    candidate_keys = [item["key"] for item in candidate_items]
                    any_of_constraint_groups.append(candidate_keys)

                    # If the value is not a wildcard, create properties for each
                    # candidate key, preserving any descriptions.
                    if value is not object:
                        for item in candidate_items:
                            prop_schema = pval.copy()
                            final_description = item["desc"] or description
                            if final_description:
                                prop_schema["description"] = final_description
                            properties[item["key"]] = prop_schema
                else:
                    # Handle Optional(Any(...)) - expand to individual properties
                    for val_item in pkey.validators:
                        if isinstance(val_item, vol.Marker):
                            if val_item.description:
                                properties[str(val_item.schema)] = pval.copy()
                                properties[str(val_item.schema)][
                                    "description"
                                ] = val_item.description
                            else:
                                properties[str(val_item)] = pval
                        else:
                            properties[str(val_item)] = pval
            elif isinstance(pkey, str):
                properties[pkey] = pval
            else:
                if pval == {"type": "object", "additionalProperties": True}:
                    pval = True
                    additional_properties = None
                if additional_properties is None:
                    additional_properties = pval

        val = {"type": "object"}
        if properties or not additional_properties:
            val["properties"] = properties
            val["required"] = required
        if additional_properties:
            val["additionalProperties"] = additional_properties

        # Generate anyOf constraints from the Cartesian product of constraint groups
        if any_of_constraint_groups:
            # Generate all combinations (Cartesian product) of the constraint groups
            val["anyOf"] = [
                {"required": list(combination)}
                for combination in itertools.product(*any_of_constraint_groups)
            ]

        return val

    if isinstance(schema, vol.All):
        val = {}
        fallback = False
        allOf = []
        for validator in schema.validators:
            v = convert_with_args(validator)
            if (
                not v
                or v in allOf
                or v == {"type": "object", "additionalProperties": True}
            ):
                continue
            if any(v[key] != val[key] for key in v.keys() & val.keys()):
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
        nullable = False
        while None in enum_values:
            enum_values.remove(None)
            nullable = True
        while NoneType in enum_values:
            enum_values.remove(NoneType)
            nullable = True
        if enum_values:
            enum_type = TYPES_MAP.get(type(enum_values[0]), "string")
        else:
            enum_type = "string"
        if nullable:
            return {"type": enum_type, "enum": enum_values, "nullable": True}
        return {"type": enum_type, "enum": enum_values}

    if schema in (
        vol.Lower,
        vol.Upper,
        vol.Capitalize,
        vol.Title,
        vol.Strip,
        vol.Email,
        vol.Url,
        vol.FqdnUrl,
    ):
        return {
            "format": schema.__name__.lower(),
        }

    if isinstance(schema, vol.Any):
        schema = schema.validators
        # Infer the enum type based on the type of the first value, but default
        # to a string as a fallback.
        if (
            None in schema or NoneType in schema
        ) and openapi_version == OpenApiVersion.V3:
            schema = [val for val in schema if val is not None and val is not NoneType]
            nullable = True
        else:
            nullable = False
        if len(schema) == 1:
            result = convert_with_args(schema[0])
        else:
            anyOf = [convert_with_args(val) for val in schema]

            # Merge nested anyOf
            tmpAnyOf = []
            for item in anyOf:
                if item.get("anyOf"):
                    tmpAnyOf.extend(item["anyOf"])
                    if item.get("nullable"):
                        nullable = True
                else:
                    tmpAnyOf.append(item)
            anyOf = tmpAnyOf

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
                    if item.get("enum"):
                        merged = False
                        for item2 in tmpAnyOf:
                            if item2.get("enum") and item.get("type") == item2.get(
                                "type"
                            ):  # Merge nested enums of the same type
                                if item.get("nullable"):
                                    item2["nullable"] = True
                                item2["enum"] = list(set(item2["enum"] + item["enum"]))
                                merged = True
                                break
                        if merged:
                            continue

                    tmpAnyOf.append(item)
                anyOf = tmpAnyOf

                # Remove excessive nullables
                null_count = 0
                if not nullable:
                    for item in anyOf:
                        if item.get("nullable") is True:
                            null_count = null_count + 1
                        if null_count > 1:
                            break

                if nullable or null_count > 1:
                    nullable = True
                    tmpAnyOf = []
                    for item in anyOf:
                        if "nullable" not in item:
                            tmpAnyOf.append(item)
                            continue
                        tmpItem = item.copy()
                        tmpItem.pop("nullable")
                        tmpAnyOf.append(tmpItem)
                    anyOf = tmpAnyOf

                if len(anyOf) == 1:
                    result = anyOf[0]
                else:
                    result = {"anyOf": anyOf}
        if nullable:
            result["nullable"] = True
        return result

    if isinstance(schema, vol.Coerce):
        schema = schema.type

    if isinstance(schema, (str, int, float, bool)):
        return {"type": TYPES_MAP[type(schema)], "enum": [schema]}

    if schema is None:
        if openapi_version == OpenApiVersion.V3_1:
            return {"type": "null"}
        return {"type": "object", "nullable": True, "description": "Must be null"}

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
                "items": ensure_default(convert_with_args(schema[0])),
            }
        return {
            "type": "array",
            "items": [ensure_default(convert_with_args(s)) for s in schema.items()],
        }

    if schema in TYPES_MAP:
        return {"type": TYPES_MAP[schema]}

    if get_origin(schema) is dict:
        if get_args(schema)[1] is Any or isinstance(get_args(schema)[1], TypeVar):
            schema = dict
        else:
            return convert_with_args({get_args(schema)[0]: get_args(schema)[1]})

    if isinstance(schema, type):
        if schema is dict:
            return {"type": "object", "additionalProperties": True}

        if schema is list or schema is set or schema is tuple:
            return {"type": "array", "items": ensure_default({})}

        if issubclass(schema, Enum):
            enum_values = list(item.value for item in schema)
            nullable = False
            while None in enum_values:
                enum_values.remove(None)
                nullable = True
            while NoneType in enum_values:
                enum_values.remove(NoneType)
                nullable = True
            if enum_values:
                enum_type = TYPES_MAP.get(type(enum_values[0]), "string")
            else:
                enum_type = "string"
            if nullable:
                return {"type": enum_type, "enum": enum_values, "nullable": True}
            return {"type": enum_type, "enum": enum_values}
        elif schema is NoneType:
            if openapi_version == OpenApiVersion.V3_1:
                return {"type": "null"}
            return {"type": "object", "nullable": True, "description": "Must be null"}

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

        return ensure_default(convert_with_args(schema))

    raise ValueError("Unable to convert schema: {}".format(schema))


def convert_to_voluptuous(schema: dict) -> vol.Schema:
    """Convert an OpenAPI Schema object to a voluptuous schema."""

    if not isinstance(schema, dict):
        raise ValueError("Invalid schema, expected a dictionary")

    for keyword in OPENAPI_UNSUPPORTED_KEYWORDS:
        if keyword in schema:
            raise ValueError(f"{keyword} is not supported")

    if (one_of := schema.get("oneOf")) is not None:
        if not isinstance(one_of, list):
            raise ValueError("Invalid schema, oneOf should be a list")
        # This implements anyOf semantics sice it matches any of the subschemas,
        # not just one of them.
        return vol.Any(*[convert_to_voluptuous(sub_schema) for sub_schema in one_of])

    if (any_of := schema.get("anyOf")) is not None:
        if not isinstance(any_of, list):
            raise ValueError("Invalid schema, anyOf should be a list")
        # If the anyOf is a list of required properties, it's a constraint on an
        # object and should be handled by the object validator.
        is_required_constraint = all(
            list(s.keys()) == ["required"] and isinstance(s["required"], list)
            for s in any_of
        )
        if not (is_required_constraint and schema.get("type") == "object"):
            return vol.Any(
                *[convert_to_voluptuous(sub_schema) for sub_schema in any_of]
            )

    if (schema_type := schema.get("type")) is None:
        raise ValueError("Invalid schema, missing type")

    if schema_type == "null":
        return vol.Schema(None)

    # Handle OpenAPI 3.1 style: type can be an array like ["string", "null"]
    if isinstance(schema_type, list):
        if len(schema_type) == 0:
            raise ValueError("Invalid schema, type array cannot be empty")

        validators = []
        for t in schema_type:
            if t == "null":
                validators.append(None)
            else:
                base_schema = schema.copy()
                base_schema["type"] = t
                validators.append(convert_to_voluptuous(base_schema))
        return vol.Any(*validators)

    if (basic_type := TYPES_MAP_REV.get(schema_type)) is not None:
        validator = basic_type

        if schema_type == "string":
            if (pattern := schema.get("pattern")) is not None:
                validator = vol.Match(re.compile(pattern))
            elif (format := schema.get("format")) is not None and format == "date-time":
                validator = vol.Datetime()
            else:
                min_length = schema.get("minLength")
                max_length = schema.get("maxLength")
                if min_length is not None or max_length is not None:
                    validator = vol.All(
                        basic_type, vol.Length(min=min_length, max=max_length)
                    )

        elif schema_type in ("integer", "number"):
            min_val = schema.get("minimum")
            max_val = schema.get("maximum")
            if min_val is not None or max_val is not None:
                validator = vol.All(basic_type, vol.Range(min=min_val, max=max_val))

        # Handle OpenAPI 3.0 nullable property
        if schema.get("nullable") is True:
            return vol.Any(validator, None)

        return validator

    if schema_type == "object":
        properties = {}
        required_properties = set(schema.get("required", []))
        for key, value in schema.get("properties", {}).items():
            value_type = convert_to_voluptuous(value)
            description: str | None = None
            if isinstance(value, dict):
                description = value.get("description")
            if key in required_properties:
                key_type = vol.Required
            else:
                key_type = vol.Optional
            properties[key_type(key, description=description)] = value_type

        if (any_of := schema.get("anyOf")) is not None:
            any_of_keys = [
                key for sub_schema in any_of for key in sub_schema.get("required", [])
            ]
            if any_of_keys:
                properties[vol.Required(vol.Any(*any_of_keys))] = object

        validator = None
        if schema.get("additionalProperties") is True:
            validator = vol.Schema(properties, extra=vol.ALLOW_EXTRA)
        else:
            validator = vol.Schema(properties)

        # Handle OpenAPI 3.0 nullable property
        if schema.get("nullable") is True:
            return vol.Any(validator, None)

        return validator

    if schema_type == "array":
        item_validator = convert_to_voluptuous(schema["items"])
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")

        if min_items is not None or max_items is not None:
            validator = vol.Schema(
                vol.All([item_validator], vol.Length(min=min_items, max=max_items))
            )
        else:
            validator = vol.Schema([item_validator])

        # Handle OpenAPI 3.0 nullable property
        if schema.get("nullable") is True:
            return vol.Any(validator, None)

        return validator

    raise ValueError("Unable to convert schema: {}".format(schema))
