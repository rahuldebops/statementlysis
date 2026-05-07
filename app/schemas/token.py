"""Pydantic schemas for token data."""

from pydantic import BaseModel


class TokenSchema(BaseModel):
    text: str
    x0: float
    x1: float
    y0: float
    y1: float
    page: int
    sequence: int = 0

    model_config = {"from_attributes": True}


class LineSchema(BaseModel):
    line_number: int
    page: int
    raw_text: str
    y_center: float
    tokens: list[TokenSchema] = []

    model_config = {"from_attributes": True}
