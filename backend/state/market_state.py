from dataclasses import dataclass
from threading import RLock
from typing import Optional

from backend.protocol.drop.messages import (
    MarketMessage,
    MarketTradingStateMessage,
)

@dataclass(frozen=True)
class MarketRecord:
    """Current reconstructed state of one market."""

    market_index: Optional[int]
    market_id: int
    market_name: Optional[str]
    market_trading_session: Optional[int]
    state: Optional[str]

    definition_sequence: int
    definition_timestamp_ns: int

    state_sequence: int
    state_timestamp_ns: int

    @property
    def last_sequence(self):
        return max(
            self.definition_sequence,
            self.state_sequence,
        )

    @property
    def last_timestamp_ns(self):
        if (
            self.state_sequence
            >= self.definition_sequence
        ):
            return self.state_timestamp_ns

        return self.definition_timestamp_ns

    def to_dict(self):
        return {
            "market_index": self.market_index,
            "market_id": self.market_id,
            "market_name": self.market_name,
            "market_trading_session": (
                self.market_trading_session
            ),
            "state": self.state,
            "definition_sequence": (
                self.definition_sequence
            ),
            "state_sequence": self.state_sequence,
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": (
                self.last_timestamp_ns
            ),
        }


class MarketStateStore:
    """Thread-safe in-memory market state store."""

    def __init__(self):
        self._markets = {}
        self._lock = RLock()

    @property
    def count(self):
        with self._lock:
            return len(self._markets)

    def apply(self, message):
        """Apply a supported DROP market message."""

        if isinstance(message, MarketMessage):
            return self._apply_market(message)

        if isinstance(
            message,
            MarketTradingStateMessage,
        ):
            return self._apply_market_state(message)

        return False

    def get_market(self, market_id):
        market_id = int(market_id)

        with self._lock:
            return self._markets.get(market_id)

    def get_markets(self):
        with self._lock:
            return tuple(
                sorted(
                    self._markets.values(),
                    key=lambda market: (
                        market.market_id
                    ),
                )
            )

    def snapshot(self):
        return [
            market.to_dict()
            for market in self.get_markets()
        ]

    def clear(self):
        with self._lock:
            self._markets.clear()

    def _apply_market(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._markets.get(
                message.market_id
            )

            if (
                current is not None
                and sequence
                <= current.definition_sequence
            ):
                return False

            if current is None:
                state = None
                state_sequence = 0
                state_timestamp_ns = 0
            else:
                state = current.state
                state_sequence = (
                    current.state_sequence
                )
                state_timestamp_ns = (
                    current.state_timestamp_ns
                )

            self._markets[message.market_id] = (
                MarketRecord(
                    market_index=(
                        message.market_index
                    ),
                    market_id=message.market_id,
                    market_name=message.market_name,
                    market_trading_session=(
                        message
                        .market_trading_session
                    ),
                    state=state,
                    definition_sequence=sequence,
                    definition_timestamp_ns=(
                        timestamp_ns
                    ),
                    state_sequence=state_sequence,
                    state_timestamp_ns=(
                        state_timestamp_ns
                    ),
                )
            )

            return True

    def _apply_market_state(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._markets.get(
                message.market_id
            )

            if (
                current is not None
                and sequence
                <= current.state_sequence
            ):
                return False

            if current is None:
                market_name = None
                market_trading_session = None
                definition_sequence = 0
                definition_timestamp_ns = 0
            else:
                market_name = current.market_name
                market_trading_session = (
                    current.market_trading_session
                )
                definition_sequence = (
                    current.definition_sequence
                )
                definition_timestamp_ns = (
                    current
                    .definition_timestamp_ns
                )

            self._markets[message.market_id] = (
                MarketRecord(
                    market_index=(
                        message.market_index
                    ),
                    market_id=message.market_id,
                    market_name=market_name,
                    market_trading_session=(
                        market_trading_session
                    ),
                    state=message.state,
                    definition_sequence=(
                        definition_sequence
                    ),
                    definition_timestamp_ns=(
                        definition_timestamp_ns
                    ),
                    state_sequence=sequence,
                    state_timestamp_ns=(
                        timestamp_ns
                    ),
                )
            )

            return True
