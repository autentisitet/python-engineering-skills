# Pydantic v2 and Settings Guide

## Choose the Boundary

| Tool | Main responsibility | Typical sources |
| --- | --- | --- |
| Standard class/dataclass | Internal state and behavior; no automatic runtime type validation | Already trusted Python values |
| `pydantic.BaseModel` | Parse/validate/serialize boundary data | Dict, JSON, API/message/file representations |
| `pydantic_settings.BaseSettings` | Load and validate application configuration | Init values, environment, dotenv, secrets/custom sources |
| `pydantic.dataclasses.dataclass` | Dataclass-shaped API with Pydantic validation | Compatibility where dataclass behavior is required |

Database rows are external representations only when the repository/adapter treats them as such. Do not make every internal or persisted object a BaseModel by default.

---

## Models and Configuration

```python
from pydantic import BaseModel, ConfigDict, Field


class UserInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    age: int = Field(ge=0, le=150)
```

Useful `ConfigDict` choices include `strict`, `extra`, `validate_assignment`, `frozen`, and `from_attributes`. Select them from the actual contract:

- `extra="ignore"` discards unknown fields, `allow` retains them, and `forbid` raises a validation error.
- `validate_assignment=True` validates later attribute assignment, but cross-object/domain operations may still need named methods.
- `frozen=True` prevents normal field assignment; it does not recursively freeze nested mutable values.
- `from_attributes=True` allows validation from object attributes; it does not make arbitrary objects semantically equivalent.
- `use_enum_values=True` populates fields with Enum values during validation. Defaults needing the same conversion may require `validate_default=True`.

`Field(...)` can express per-field constraints and metadata. `typing.Annotated[T, Field(...)]` is a supported Pydantic pattern: Annotated metadata alone is inert to Python, but Pydantic consumes recognized metadata and validates it.

Use `field_validator` for one-field normalization/constraints and `model_validator` for whole-model before/after rules. These Pydantic decorators/configurations do not add validation to an ordinary class or standard-library dataclass.

---

## Nested Data and Serialization

Nested dictionaries/lists can be validated into nested Pydantic models according to annotations. Define actual model types rather than accepting `Any` throughout the tree.

| Operation | Pydantic v2 API |
| --- | --- |
| Python representation | `model_dump()` |
| JSON text | `model_dump_json()` |
| Validate Python object/mapping | `model_validate()` |
| Validate JSON text/bytes | `model_validate_json()` |

These are not the same as standard `dataclasses.asdict()` or `json.dumps()`; keep boundary serialization explicit.

---

## BaseSettings

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    username: str
    password: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MYAPP_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    debug: bool = False
    database: DatabaseSettings
```

`env_nested_delimiter="__"` can map names such as `MYAPP_DATABASE__HOST` into nested models. Source precedence and dotenv extra-field behavior can vary with explicit settings/custom sources, so verify the installed pydantic-settings version and configuration. Do not log secret values.

Official references:

- <https://docs.pydantic.dev/latest/concepts/models/>
- <https://docs.pydantic.dev/latest/concepts/fields/>
- <https://docs.pydantic.dev/latest/concepts/validators/>
- <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
- <https://docs.pydantic.dev/latest/concepts/dataclasses/>
