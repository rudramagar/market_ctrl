from dataclasses import dataclass
from threading import RLock
from typing import Optional

from backend.protocol.drop.messages import (
    MarketMessage,
    MarketTradingPhaseMessage,
    MarketTradingStateMessage,
)


MARKET_PHASE_NAMES = {
    0: "CLOSED",
    1: "STARTING",
    2: "OPEN",
    3: "HALTED",
}


@dataclass(frozen=True)
class MarketRecord:
    """Current reconstructed state of one market."""

    market_index: Optional[int]
    market_id: int
    market_name: Optional[str]
    market_trading_session: Optional[int]

    state: Optional[str]
    phase: Optional[int]

    definition_sequence: int
    definition_timestamp_ns: int

    state_sequence: int
    state_timestamp_ns: int

    phase_sequence: int
    phase_timestamp_ns: int

    @property
    def phase_name(self):
        if self.phase is None:
            return None

        return MARKET_PHASE_NAMES.get(
            self.phase,
            "UNKNOWN",
        )

    @property
    def last_sequence(self):
        return max(
            self.definition_sequence,
            self.state_sequence,
            self.phase_sequence,
        )

    @property
    def last_timestamp_ns(self):
        last_sequence = self.last_sequence

        if last_sequence == self.phase_sequence:
            return self.phase_timestamp_ns

        if last_sequence == self.state_sequence:
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
            "phase": self.phase,
            "phase_name": self.phase_name,
            "definition_sequence": (
                self.definition_sequence
            ),
            "definition_timestamp_ns": (
                self.definition_timestamp_ns
            ),
            "state_sequence": self.state_sequence,
            "state_timestamp_ns": (
                self.state_timestamp_ns
            ),
            "phase_sequence": self.phase_sequence,
            "phase_timestamp_ns": (
                self.phase_timestamp_ns
            ),
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
            return self._apply_market_state(
                message
            )

        if isinstance(
            message,
            MarketTradingPhaseMessage,
        ):
            return self._apply_market_phase(
                message
            )

        return False

    def get_market(self, market_id):
        market_id = int(market_id)

        with self._lock:
            return self._markets.get(
                market_id
            )

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

    def restore(self, records):
        """
        Replace the current market state from a snapshot.

        All records are validated before the live state
        is changed.
        """

        if not isinstance(records, list):
            raise ValueError(
                "market snapshot must be a list"
            )

        restored_markets = {}

        for position, values in enumerate(
            records
        ):
            if not isinstance(values, dict):
                raise ValueError(
                    "market snapshot record %d "
                    "must be an object"
                    % position
                )

            record = self._restore_record(
                values,
                position,
            )

            if (
                record.market_id
                in restored_markets
            ):
                raise ValueError(
                    "duplicate market ID "
                    "in snapshot: %d"
                    % record.market_id
                )

            restored_markets[
                record.market_id
            ] = record

        with self._lock:
            self._markets = restored_markets

        return len(restored_markets)

    def clear(self):
        """Clear all reconstructed market state."""

        with self._lock:
            self._markets.clear()

    @classmethod
    def _restore_record(
        cls,
        values,
        position,
    ):
        market_id = cls._required_int(
            values,
            "market_id",
            position,
        )

        if market_id <= 0:
            raise ValueError(
                "market snapshot record %d has "
                "invalid market_id: %d"
                % (
                    position,
                    market_id,
                )
            )

        definition_sequence = (
            cls._required_int(
                values,
                "definition_sequence",
                position,
            )
        )
        definition_timestamp_ns = (
            cls._required_int(
                values,
                "definition_timestamp_ns",
                position,
            )
        )

        state_sequence = cls._required_int(
            values,
            "state_sequence",
            position,
        )
        state_timestamp_ns = cls._required_int(
            values,
            "state_timestamp_ns",
            position,
        )

        phase_sequence = cls._required_int(
            values,
            "phase_sequence",
            position,
        )
        phase_timestamp_ns = cls._required_int(
            values,
            "phase_timestamp_ns",
            position,
        )

        numeric_values = (
            definition_sequence,
            definition_timestamp_ns,
            state_sequence,
            state_timestamp_ns,
            phase_sequence,
            phase_timestamp_ns,
        )

        if any(
            value < 0
            for value in numeric_values
        ):
            raise ValueError(
                "market snapshot record %d has "
                "a negative sequence or timestamp"
                % position
            )

        state = cls._optional_string(
            values,
            "state",
            position,
        )
        phase = cls._optional_int(
            values,
            "phase",
            position,
        )

        if phase not in (
            None,
            0,
            1,
            2,
            3,
        ):
            raise ValueError(
                "market snapshot record %d has "
                "invalid phase: %r"
                % (
                    position,
                    phase,
                )
            )

        return MarketRecord(
            market_index=cls._optional_int(
                values,
                "market_index",
                position,
            ),
            market_id=market_id,
            market_name=cls._optional_string(
                values,
                "market_name",
                position,
            ),
            market_trading_session=(
                cls._optional_int(
                    values,
                    "market_trading_session",
                    position,
                )
            ),
            state=state,
            phase=phase,
            definition_sequence=(
                definition_sequence
            ),
            definition_timestamp_ns=(
                definition_timestamp_ns
            ),
            state_sequence=state_sequence,
            state_timestamp_ns=(
                state_timestamp_ns
            ),
            phase_sequence=phase_sequence,
            phase_timestamp_ns=(
                phase_timestamp_ns
            ),
        )

    @staticmethod
    def _required_int(
        values,
        name,
        position,
    ):
        if name not in values:
            raise ValueError(
                "market snapshot record %d is "
                "missing %s"
                % (
                    position,
                    name,
                )
            )

        value = values[name]

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
        ):
            raise ValueError(
                "market snapshot record %d field "
                "%s must be an integer"
                % (
                    position,
                    name,
                )
            )

        return value

    @staticmethod
    def _optional_int(
        values,
        name,
        position,
    ):
        value = values.get(name)

        if value is None:
            return None

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
        ):
            raise ValueError(
                "market snapshot record %d field "
                "%s must be an integer or null"
                % (
                    position,
                    name,
                )
            )

        return value

    @staticmethod
    def _optional_string(
        values,
        name,
        position,
    ):
        value = values.get(name)

        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                "market snapshot record %d field "
                "%s must be a string or null"
                % (
                    position,
                    name,
                )
            )

        return value

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

                phase = None
                phase_sequence = 0
                phase_timestamp_ns = 0

            else:
                state = current.state
                state_sequence = (
                    current.state_sequence
                )
                state_timestamp_ns = (
                    current.state_timestamp_ns
                )

                phase = current.phase
                phase_sequence = (
                    current.phase_sequence
                )
                phase_timestamp_ns = (
                    current.phase_timestamp_ns
                )

            self._markets[message.market_id] = (
                MarketRecord(
                    market_index=(
                        message.market_index
                    ),
                    market_id=message.market_id,
                    market_name=(
                        message.market_name
                    ),
                    market_trading_session=(
                        message
                        .market_trading_session
                    ),
                    state=state,
                    phase=phase,
                    definition_sequence=sequence,
                    definition_timestamp_ns=(
                        timestamp_ns
                    ),
                    state_sequence=(
                        state_sequence
                    ),
                    state_timestamp_ns=(
                        state_timestamp_ns
                    ),
                    phase_sequence=(
                        phase_sequence
                    ),
                    phase_timestamp_ns=(
                        phase_timestamp_ns
                    ),
                )
            )

            return True

    def _apply_market_state(
        self,
        message,
    ):
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

                phase = None
                phase_sequence = 0
                phase_timestamp_ns = 0

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

                phase = current.phase
                phase_sequence = (
                    current.phase_sequence
                )
                phase_timestamp_ns = (
                    current.phase_timestamp_ns
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
                    phase=phase,
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
                    phase_sequence=(
                        phase_sequence
                    ),
                    phase_timestamp_ns=(
                        phase_timestamp_ns
                    ),
                )
            )

            return True

    def _apply_market_phase(
        self,
        message,
    ):
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
                <= current.phase_sequence
            ):
                return False

            if current is None:
                market_name = None
                market_trading_session = None

                state = None
                state_sequence = 0
                state_timestamp_ns = 0

                definition_sequence = 0
                definition_timestamp_ns = 0

            else:
                market_name = current.market_name
                market_trading_session = (
                    current.market_trading_session
                )

                state = current.state
                state_sequence = (
                    current.state_sequence
                )
                state_timestamp_ns = (
                    current.state_timestamp_ns
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
                    state=state,
                    phase=message.phase,
                    definition_sequence=(
                        definition_sequence
                    ),
                    definition_timestamp_ns=(
                        definition_timestamp_ns
                    ),
                    state_sequence=(
                        state_sequence
                    ),
                    state_timestamp_ns=(
                        state_timestamp_ns
                    ),
                    phase_sequence=sequence,
                    phase_timestamp_ns=(
                        timestamp_ns
                    ),
                )
            )

            return True
