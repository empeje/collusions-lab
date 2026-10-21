"""Double-auction scenario (Milestone 6A): continuous double auction (CDA).

Independent reimplementation of the published mechanics of arXiv:2507.01413. See
``NOTICE.md`` at the repo root for the licensing stance.
"""

from .cda import (
    DoubleAuctionConfig,
    DoubleAuctionMarket,
    DoubleAuctionState,
    Order,
)

__all__ = [
    "DoubleAuctionConfig",
    "DoubleAuctionMarket",
    "DoubleAuctionState",
    "Order",
]
