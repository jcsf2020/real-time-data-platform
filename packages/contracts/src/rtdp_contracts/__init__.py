from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class MarketEvent(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    event_type: Literal["trade"] = "trade"
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    event_timestamp: datetime
