from dataclasses import dataclass
from threading import RLock

from backend.protocol.drop.messages import (
    UserMarketMessage,
    UserTypeMessage,
)


@dataclass(frozen=True)
class UserTypeRecord:
    """Latest definition of one user type."""

    user_type_index: int
    user_type_id: int
    user_type_name: str
    sequence: int
    timestamp_ns: int

    @property
    def last_sequence(self):
        return self.sequence

    @property
    def last_timestamp_ns(self):
        return self.timestamp_ns

    def to_dict(self):
        return {
            "user_type_index": self.user_type_index,
            "user_type_id": self.user_type_id,
            "user_type_name": self.user_type_name,
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": self.last_timestamp_ns,
        }


@dataclass(frozen=True)
class UserMarketRecord:
    """Latest user-to-market relationship."""

    user_market_index: int
    user_id: int
    market_id: int
    sequence: int
    timestamp_ns: int

    @property
    def last_sequence(self):
        return self.sequence

    @property
    def last_timestamp_ns(self):
        return self.timestamp_ns

    def to_dict(self):
        return {
            "user_market_index": self.user_market_index,
            "user_id": self.user_id,
            "market_id": self.market_id,
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": self.last_timestamp_ns,
        }


class ReferenceStateStore:
    """Thread-safe user-type and user-market store."""

    def __init__(self):
        self._user_types = {}
        self._user_markets = {}
        self._lock = RLock()

    @property
    def user_type_count(self):
        with self._lock:
            return len(self._user_types)

    @property
    def user_market_count(self):
        with self._lock:
            return len(self._user_markets)

    def apply(self, message):
        if isinstance(message, UserTypeMessage):
            return self._apply_user_type(message)

        if isinstance(message, UserMarketMessage):
            return self._apply_user_market(message)

        return False

    def get_user_type(self, user_type_id):
        user_type_id = int(user_type_id)

        with self._lock:
            return self._user_types.get(user_type_id)

    def get_user_types(self):
        with self._lock:
            return tuple(
                sorted(
                    self._user_types.values(),
                    key=lambda record: (
                        record.user_type_id
                    ),
                )
            )

    def get_user_market(
        self,
        user_market_index,
    ):
        user_market_index = int(
            user_market_index
        )

        with self._lock:
            return self._user_markets.get(
                user_market_index
            )

    def get_user_markets(self, user_id):
        user_id = int(user_id)

        with self._lock:
            records = [
                record
                for record
                in self._user_markets.values()
                if record.user_id == user_id
            ]

        return tuple(
            sorted(
                records,
                key=lambda record: (
                    record.market_id,
                    record.user_market_index,
                ),
            )
        )

    def get_market_users(self, market_id):
        market_id = int(market_id)

        with self._lock:
            records = [
                record
                for record
                in self._user_markets.values()
                if record.market_id == market_id
            ]

        return tuple(
            sorted(
                records,
                key=lambda record: (
                    record.user_id,
                    record.user_market_index,
                ),
            )
        )

    def snapshot(self):
        return {
            "user_types": [
                record.to_dict()
                for record
                in self.get_user_types()
            ],
            "user_markets": [
                record.to_dict()
                for record
                in self._get_user_markets()
            ],
        }

    def clear(self):
        with self._lock:
            self._user_types.clear()
            self._user_markets.clear()

    def _get_user_markets(self):
        with self._lock:
            return tuple(
                sorted(
                    self._user_markets.values(),
                    key=lambda record: (
                        record.user_id,
                        record.market_id,
                        record.user_market_index,
                    ),
                )
            )

    def _apply_user_type(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._user_types.get(
                message.user_type_id
            )

            if (
                current is not None
                and sequence <= current.sequence
            ):
                return False

            self._user_types[
                message.user_type_id
            ] = UserTypeRecord(
                user_type_index=(
                    message.user_type_index
                ),
                user_type_id=message.user_type_id,
                user_type_name=(
                    message.user_type_name
                ),
                sequence=sequence,
                timestamp_ns=timestamp_ns,
            )

            return True

    def _apply_user_market(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._user_markets.get(
                message.user_market_index
            )

            if (
                current is not None
                and sequence <= current.sequence
            ):
                return False

            self._user_markets[
                message.user_market_index
            ] = UserMarketRecord(
                user_market_index=(
                    message.user_market_index
                ),
                user_id=message.user_id,
                market_id=message.market_id,
                sequence=sequence,
                timestamp_ns=timestamp_ns,
            )

            return True
