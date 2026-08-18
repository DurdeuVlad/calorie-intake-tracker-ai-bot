from enum import Enum


class QuantityUnit(str, Enum):
    G = "g"
    ML = "ml"
    PORTION = "portion"
    UNSPECIFIED = "unspecified"

    @classmethod
    def from_database_value(cls, value: str | None) -> "QuantityUnit":
        if value is None or not value.strip():
            return cls.UNSPECIFIED
        try:
            return cls(value.strip())
        except ValueError as exc:
            raise ValueError(f"Unrecognized quantity unit: {value}") from exc
