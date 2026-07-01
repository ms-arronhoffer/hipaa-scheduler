"""Shared Pydantic v2 base + common response shapes."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int
