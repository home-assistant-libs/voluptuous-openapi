from enum import Enum

import voluptuous as vol

from voluptuous_openapi import UNSUPPORTED, convert


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
    assert {"enum": ["beer", "wine"]} == convert(vol.Schema(vol.In(["beer", "wine"])))


def test_in_dict():
    assert {
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
    for value in True, False, "Hello", 1, None:
        assert {"enum": [value]} == convert(vol.Schema(value))


def test_enum():
    class TestEnum(Enum):
        ONE = "one"
        TWO = 2

    assert {"enum": ["one", 2]} == convert(vol.Schema(vol.Coerce(TestEnum)))


def test_list():
    assert {
        "type": "array",
        "items": {"type": "string"},
    } == convert(vol.Schema([str]))


def test_key_any():
    assert {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "At least one of ('name', 'area') must be provided",
            },
            "area": {
                "type": "string",
                "description": "At least one of ('name', 'area') must be provided",
            },
        },
        "required": [],
    } == convert(vol.Schema({vol.Any("name", "area"): str}))
