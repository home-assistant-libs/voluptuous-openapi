# Voluptuous OpenAPI

Convert Voluptuous schemas to [OpenAPI Schema object](https://spec.openapis.org/oas/v3.0.3#schema-object).

```python
schema = {}
schema[vol.Required('name')] = vol.All(str, vol.Length(min=5))
schema[vol.Required('age', description='Age in full years')] = vol.All(vol.Coerce(int), vol.Range(min=18))
schema[vol.Optional('hobby', default='not specified')] = str
schema = vol.Schema(schema)
```

becomes

```json
{
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "minLength": 5,
        },
        "age": {
            "type": "integer",
            "minimum": 18,
            "description": "Age in full years",
        },
        "hobby": {
            "type": "string",
            "default": "not specified",
        },
    },
    "required": ["name", "age"],
}
```

See the tests for more examples.

## Custom serializer

You can pass a custom serializer to be able to process custom validators. If the serializer returns `UNSUPPORTED`, it will return to normal processing. Example:

```python

from voluptuous_openai import UNSUPPORTED, convert

def custom_convert(value):
    if value is my_custom_validator:
        return {'pattern': '^[a-zA-Z0-9]$'}
        
    return UNSUPPORTED

convert(value, custom_serializer=custom_convert)
```
