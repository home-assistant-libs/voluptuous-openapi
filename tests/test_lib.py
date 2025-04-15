from enum import Enum
from typing import Any, TypeVar

import pytest
import voluptuous as vol

from voluptuous_openapi import UNSUPPORTED, convert, convert_to_voluptuous


def test_int_schema():
    for value in int, vol.Coerce(int):
        assert {"type": "integer"} == convert(vol.Schema(value))


def test_str_schema():
    for value in str, vol.Coerce(str):
        assert {"type": "string"} == convert(vol.Schema(value))


def test_float_schema():
    for value in float, vol.Coerce(float):
        assert {"type": "number"} == convert(vol.Schema(value))


def test_bool_schema():
    for value in bool, vol.Coerce(bool):
        assert {"type": "boolean"} == convert(vol.Schema(value))


def test_integer_clamp():
    assert {
        "type": "integer",
        "minimum": 100,
        "maximum": 1000,
    } == convert(vol.Schema(vol.All(vol.Coerce(int), vol.Clamp(min=100, max=1000))))


def test_length():
    assert {
        "type": "string",
        "minLength": 100,
        "maxLength": 1000,
    } == convert(vol.Schema(vol.All(vol.Coerce(str), vol.Length(min=100, max=1000))))


def test_datetime():
    assert {
        "type": "string",
        "format": "date-time",
    } == convert(vol.Schema(vol.Datetime()))


def test_in():
    assert {"type": "string", "enum": ["beer", "wine"]} == convert(
        vol.Schema(vol.In(["beer", "wine"]))
    )


def test_in_integer():
    assert {"type": "integer", "enum": [1, 2]} == convert(vol.Schema(vol.In([1, 2])))


def test_in_dict():
    assert {
        "type": "string",
        "enum": ["en_US", "zh_CN"],
    } == convert(
        vol.Schema(
            vol.In({"en_US": "American English", "zh_CN": "Chinese (Simplified)"})
        )
    )


def test_dict():
    assert {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 5,
            },
            "age": {
                "type": "integer",
                "minimum": 18,
            },
            "hobby": {
                "type": "string",
                "default": "not specified",
            },
        },
        "required": ["name", "age"],
    } == convert(
        vol.Schema(
            {
                vol.Required("name"): vol.All(str, vol.Length(min=5)),
                vol.Required("age"): vol.All(vol.Coerce(int), vol.Range(min=18)),
                vol.Optional("hobby", default="not specified"): str,
            }
        )
    )

    assert {"type": "object", "additionalProperties": True} == convert(vol.Schema(dict))

    assert {"type": "object", "additionalProperties": True} == convert(
        vol.Schema(dict[str, Any])
    )

    assert {"type": "object", "additionalProperties": {"type": "integer"}} == convert(
        vol.Schema({str: int})
    )

    assert {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
        "required": [],
        "additionalProperties": {"type": "string"},
    } == convert(vol.Schema({"x": int, str: str}))

    assert {"type": "object", "properties": {}, "required": []} == convert(
        vol.Schema({})
    )

    def string(x: str) -> str:
        return x

    assert {"type": "object", "additionalProperties": {"type": "string"}} == convert(
        vol.Schema({string: string})
    )
    assert {"type": "object", "additionalProperties": True} == convert(
        vol.Schema(object)
    )
    assert {"type": "object", "additionalProperties": True} == convert(
        vol.Schema({string: object})
    )


def test_tuple():
    assert {"type": "array", "items": {"type": "string"}} == convert(vol.Schema(tuple))
    assert {"type": "array", "items": {"type": "string"}} == convert(
        vol.Schema(tuple[Any])
    )
    assert {"type": "array", "items": {"type": "integer"}} == convert(
        vol.Schema(tuple[int])
    )


def test_marker_description():
    assert {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Description of name",
            },
        },
        "required": ["name"],
    } == convert(
        vol.Schema(
            {
                vol.Required("name", description="Description of name"): str,
            }
        )
    )


def test_lower():
    assert {
        "type": "string",
        "format": "lower",
    } == convert(vol.Schema(vol.All(vol.Lower, str)))


def test_upper():
    assert {
        "type": "string",
        "format": "upper",
    } == convert(vol.Schema(vol.All(vol.Upper, str)))


def test_capitalize():
    assert {
        "type": "string",
        "format": "capitalize",
    } == convert(vol.Schema(vol.All(vol.Capitalize, str)))


def test_title():
    assert {
        "type": "string",
        "format": "title",
    } == convert(vol.Schema(vol.All(vol.Title, str)))


def test_strip():
    assert {
        "type": "string",
        "format": "strip",
    } == convert(vol.Schema(vol.All(vol.Strip, str)))


def test_email():
    assert {
        "type": "string",
        "format": "email",
    } == convert(vol.Schema(vol.All(vol.Email, str)))


def test_url():
    assert {
        "type": "string",
        "format": "url",
    } == convert(vol.Schema(vol.All(vol.Url, str)))


def test_fqdnurl():
    assert {
        "type": "string",
        "format": "fqdnurl",
    } == convert(vol.Schema(vol.All(vol.FqdnUrl, str)))


def test_maybe():
    assert {
        "type": "string",
        "nullable": True,
    } == convert(vol.Schema(vol.Maybe(str)))


def test_custom_serializer():
    def custem_serializer(schema):
        if schema is str:
            return {"pattern": "[A-Z]{1,8}\\.[A-Z]{3,3}", "type": "string"}
        return UNSUPPORTED

    assert {
        "type": "string",
        "pattern": "[A-Z]{1,8}\\.[A-Z]{3,3}",
        "format": "upper",
    } == convert(
        vol.Schema(vol.All(vol.Upper, str)), custom_serializer=custem_serializer
    )


def test_constant():
    assert {"type": "boolean", "enum": [True]} == convert(vol.Schema(True))
    assert {"type": "boolean", "enum": [False]} == convert(vol.Schema(False))
    assert {"type": "string", "enum": ["Hello"]} == convert(vol.Schema("Hello"))
    assert {"type": "integer", "enum": [1]} == convert(vol.Schema(1))
    assert {"type": "number", "enum": [1.5]} == convert(vol.Schema(1.5))
    assert {
        "type": "object",
        "nullable": True,
        "description": "Must be null",
    } == convert(vol.Schema(None))
    assert {
        "type": "object",
        "nullable": True,
        "description": "Must be null",
    } == convert(vol.Schema(type(None)))


def test_enum():
    class StringEnum(Enum):
        ONE = "one"
        TWO = "two"

    assert {"type": "string", "enum": ["one", "two"]} == convert(
        vol.Schema(vol.Coerce(StringEnum))
    )

    class IntEnum(Enum):
        ONE = 1
        TWO = 2

    assert {"type": "integer", "enum": [1, 2]} == convert(
        vol.Schema(vol.Coerce(IntEnum))
    )


def test_list():
    assert {
        "type": "array",
        "items": {"type": "string"},
    } == convert(vol.Schema([str]))

    assert {"type": "array", "items": {"type": "string"}} == convert(vol.Schema(list))

    assert {"type": "array", "items": {"type": "string"}} == convert(
        vol.Schema(list[Any])
    )

    assert {"type": "array", "items": {"type": "integer"}} == convert(
        vol.Schema(list[int])
    )


def test_any_of():
    assert {"anyOf": [{"type": "number"}, {"type": "integer"}]} == convert(
        vol.Any(float, int)
    )

    assert {"anyOf": [{"type": "number"}, {"type": "integer"}]} == convert(
        vol.Any(float, int, float, int, int)
    )

    assert {"type": "object", "additionalProperties": True} == convert(
        vol.Any(float, int, object)
    )

    assert {"type": "integer", "nullable": True, "enum": [1, 2]} == convert(
        vol.Schema(vol.In([1, 2, None]))
    )

    assert {"type": "integer", "enum": [1, 2, 3]} == convert(
        vol.Schema(vol.Any(1, 2, 3))
    )

    assert {
        "anyOf": [{"type": "number"}, {"type": "integer"}, {"type": "string"}]
    } == convert(
        vol.Any(
            vol.Any(float, int), vol.Any(int, float), vol.Any(float, vol.Any(int, str))
        )
    )

    assert {
        "anyOf": [{"type": "number"}, {"type": "integer"}],
        "nullable": True,
    } == convert(vol.Any(vol.Maybe(float), vol.Maybe(int)))


def test_all_of():
    assert {"allOf": [{"minimum": 5}, {"minimum": 10}]} == convert(
        vol.All(vol.Range(min=5), vol.Range(min=10))
    )

    assert {"type": "string"} == convert(vol.All(object, str))

    assert {"type": "object", "additionalProperties": {"type": "string"}} == convert(
        vol.All(object, {str: str})
    )

    assert {"maximum": 10, "minimum": 5, "type": "number"} == convert(
        vol.All(vol.Range(min=5), vol.Range(max=10))
    )

    assert {"maximum": 10, "minimum": 5, "type": "number"} == convert(
        vol.All(
            vol.All(vol.Range(min=5), float),
            vol.All(vol.All(vol.Range(max=10), float), float),
        )
    )


def test_key_any():
    assert {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
            },
            "area": {
                "type": "string",
                "description": "The ID or the area",
            },
        },
        "required": [],
    } == convert(
        vol.Schema(
            {
                vol.Any(
                    "name", vol.Optional("area", description="The ID or the area")
                ): str
            }
        )
    )

    assert {
        "properties": {
            "conversation_command": {"type": "string"},
            "hours": {"type": "integer"},
            "minutes": {"type": "integer"},
            "name": {"type": "string"},
            "seconds": {"type": "integer"},
        },
        "required": [],
        "type": "object",
    } == convert(
        {
            vol.Required(vol.Any("hours", "minutes", "seconds")): int,
            vol.Optional("name"): str,
            vol.Optional("conversation_command"): str,
        }
    )


def test_function():
    def validator(data):
        return data

    assert {
        "type": "object",
        "properties": {"test_data": {"type": "string"}},
        "required": [],
    } == convert(vol.Schema({"test_data": validator}))

    def validator_str(data: str):
        return data

    assert {"type": "string"} == convert(vol.Schema(validator_str))

    def validator_any(data: Any):
        return data

    assert {} == convert(validator_any)
    assert {"type": "integer"} == convert(vol.All(vol.Coerce(int), lambda x: x / 100))

    def validator_nullable(data: float | None):
        return data

    assert {"type": "number", "nullable": True} == convert(
        vol.Schema(validator_nullable)
    )

    def validator_union(data: float | int):
        return data

    assert {"anyOf": [{"type": "number"}, {"type": "integer"}]} == convert(
        vol.Schema(validator_union)
    )

    _T = TypeVar("_T")

    def validator_nullable_2(value: _T | None):
        return value

    assert {
        "type": "object",
        "properties": {"var": {"type": "array", "items": {"type": "string"}}},
        "required": [],
    } == convert(vol.Schema({"var": vol.All(validator_nullable_2, [validator_any])}))

    def validator_list_int(value: list[int]):
        return value

    assert {"type": "array", "items": {"type": "integer"}} == convert(
        validator_list_int
    )

    def validator_list_any(value: list[Any]):
        return value

    assert {"type": "array", "items": {"type": "string"}} == convert(validator_list_any)

    def validator_list(value: list):
        return value

    assert {"type": "array", "items": {"type": "string"}} == convert(validator_list)

    def validator_set_int(value: set[int]):
        return value

    assert {"type": "array", "items": {"type": "integer"}} == convert(validator_set_int)

    def validator_set_any(value: set[Any]):
        return value

    assert {"type": "array", "items": {"type": "string"}} == convert(validator_set_any)

    def validator_set(value: set):
        return value

    assert {"type": "array", "items": {"type": "string"}} == convert(validator_set)

    def validator_dict(value: dict):
        return value

    assert {"type": "object", "additionalProperties": True} == convert(validator_dict)

    def validator_dict_int(value: dict[str, int]):
        return value

    assert {"type": "object", "additionalProperties": {"type": "integer"}} == convert(
        validator_dict_int
    )


def test_nested_in_list():
    assert {
        "properties": {
            "drink": {
                "type": "array",
                "items": {"type": "string", "enum": ["beer", "wine"]},
            },
        },
        "required": [],
        "type": "object",
    } == convert(vol.Schema({vol.Optional("drink"): [vol.In(["beer", "wine"])]}))

    assert {"type": "integer", "enum": [1, 2, 3]} == convert(
        vol.Schema(vol.In([1, 2, 3]))
    )


def test_reverse_int_schema():
    assert convert_to_voluptuous({"type": "integer"}) == int


def test_reverse_str_schema():
    assert convert_to_voluptuous({"type": "string"}) == str


def test_reverse_float_schema():
    assert convert_to_voluptuous({"type": "number"}) == float


def test_reverse_bool_schema():
    assert convert_to_voluptuous({"type": "boolean"}) == bool


def test_reverse_datetime():
    validator = convert_to_voluptuous(
        {
            "type": "string",
            "format": "date-time",
        }
    )
    validator("2025-01-01T12:32:55.11Z")

    with pytest.raises(vol.Invalid):
        validator("2021-01-01")
    with pytest.raises(vol.Invalid):
        validator("abc")


def test_reverse_unknown_type():
    with pytest.raises(ValueError):
        convert_to_voluptuous({})

    with pytest.raises(ValueError):
        convert_to_voluptuous({"type": "unknown"})


def test_convert_to_voluptuous_wrong_type() -> None:
    """Test calling with the wrong type"""

    with pytest.raises(ValueError):
        convert_to_voluptuous({"oneOf": ["integer"]})

    with pytest.raises(ValueError):
        convert_to_voluptuous({"oneOf": "integer"})

    with pytest.raises(ValueError):
        convert_to_voluptuous("a")


def test_unsupported_features() -> None:
    """Test converting a mixed aray type."""

    with pytest.raises(ValueError):
        convert_to_voluptuous({"type": "integer", "multipleOf": 2})

    with pytest.raises(ValueError):
        convert_to_voluptuous({"type": "array", "items": {"minItems": 1}})


def test_mixed_type_list() -> None:
    """Test converting a mixed aray type."""
    validator = convert_to_voluptuous(
        {"type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "integer"}]}}
    )

    validator(["a", "b"])
    validator([1, 2])
    validator(["a", 1, "b", 2])

    with pytest.raises(vol.Invalid):
        validator("abc")

    with pytest.raises(vol.Invalid):
        validator(123)


@pytest.mark.parametrize(
    "required",
    [
        (["query"]),
        ([]),
    ],
)
def test_convert_to_voluptuous_marker_description(required: list[str]):
    schema = convert_to_voluptuous(
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The query to search for"},
                "max_results": {
                    "type": "number",
                    "description": "The maximum number of results to return",
                },
            },
            "required": required,
        }
    )
    assert [(key, key.description) for key in schema.schema.keys()] == [
        ("query", "The query to search for"),
        ("max_results", "The maximum number of results to return"),
    ]
