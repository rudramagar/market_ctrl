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
            return self._user_types.get(
                user_type_id
            )

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

    def restore(self, snapshot):
        """
        Replace reference state from a snapshot.

        All records are validated before the live
        state is changed.
        """

        if not isinstance(snapshot, dict):
            raise ValueError(
                "reference snapshot must be an object"
            )

        user_types = snapshot.get(
            "user_types"
        )
        user_markets = snapshot.get(
            "user_markets"
        )

        if not isinstance(user_types, list):
            raise ValueError(
                "user_types snapshot must be a list"
            )

        if not isinstance(user_markets, list):
            raise ValueError(
                "user_markets snapshot must be a list"
            )

        restored_user_types = {}
        restored_user_markets = {}

        for position, values in enumerate(
            user_types
        ):
            record = self._restore_user_type(
                values,
                position,
            )

            if (
                record.user_type_id
                in restored_user_types
            ):
                raise ValueError(
                    "duplicate user type ID "
                    "in snapshot: %d"
                    % record.user_type_id
                )

            restored_user_types[
                record.user_type_id
            ] = record

        for position, values in enumerate(
            user_markets
        ):
            record = self._restore_user_market(
                values,
                position,
            )

            if (
                record.user_market_index
                in restored_user_markets
            ):
                raise ValueError(
                    "duplicate user-market index "
                    "in snapshot: %d"
                    % record.user_market_index
                )

            restored_user_markets[
                record.user_market_index
            ] = record

        with self._lock:
            self._user_types = (
                restored_user_types
            )
            self._user_markets = (
                restored_user_markets
            )

        return {
            "user_types": len(
                restored_user_types
            ),
            "user_markets": len(
                restored_user_markets
            ),
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

    @classmethod
    def _restore_user_type(
        cls,
        values,
        position,
    ):
        cls._require_object(
            values,
            "user type",
            position,
        )

        user_type_index = cls._required_int(
            values,
            "user_type_index",
            "user type",
            position,
        )
        user_type_id = cls._required_int(
            values,
            "user_type_id",
            "user type",
            position,
        )
        user_type_name = cls._required_string(
            values,
            "user_type_name",
            "user type",
            position,
        )
        sequence = cls._required_int(
            values,
            "last_sequence",
            "user type",
            position,
        )
        timestamp_ns = cls._required_int(
            values,
            "last_timestamp_ns",
            "user type",
            position,
        )

        if user_type_index < 0:
            raise ValueError(
                "user type snapshot record %d has "
                "invalid user_type_index: %d"
                % (
                    position,
                    user_type_index,
                )
            )

        if user_type_id <= 0:
            raise ValueError(
                "user type snapshot record %d has "
                "invalid user_type_id: %d"
                % (
                    position,
                    user_type_id,
                )
            )

        if sequence < 0 or timestamp_ns < 0:
            raise ValueError(
                "user type snapshot record %d has "
                "a negative sequence or timestamp"
                % position
            )

        return UserTypeRecord(
            user_type_index=user_type_index,
            user_type_id=user_type_id,
            user_type_name=user_type_name,
            sequence=sequence,
            timestamp_ns=timestamp_ns,
        )

    @classmethod
    def _restore_user_market(
        cls,
        values,
        position,
    ):
        cls._require_object(
            values,
            "user-market",
            position,
        )

        user_market_index = cls._required_int(
            values,
            "user_market_index",
            "user-market",
            position,
        )
        user_id = cls._required_int(
            values,
            "user_id",
            "user-market",
            position,
        )
        market_id = cls._required_int(
            values,
            "market_id",
            "user-market",
            position,
        )
        sequence = cls._required_int(
            values,
            "last_sequence",
            "user-market",
            position,
        )
        timestamp_ns = cls._required_int(
            values,
            "last_timestamp_ns",
            "user-market",
            position,
        )

        if user_market_index < 0:
            raise ValueError(
                "user-market snapshot record %d has "
                "invalid user_market_index: %d"
                % (
                    position,
                    user_market_index,
                )
            )

        if user_id <= 0:
            raise ValueError(
                "user-market snapshot record %d has "
                "invalid user_id: %d"
                % (
                    position,
                    user_id,
                )
            )

        if market_id <= 0:
            raise ValueError(
                "user-market snapshot record %d has "
                "invalid market_id: %d"
                % (
                    position,
                    market_id,
                )
            )

        if sequence < 0 or timestamp_ns < 0:
            raise ValueError(
                "user-market snapshot record %d has "
                "a negative sequence or timestamp"
                % position
            )

        return UserMarketRecord(
            user_market_index=(
                user_market_index
            ),
            user_id=user_id,
            market_id=market_id,
            sequence=sequence,
            timestamp_ns=timestamp_ns,
        )

    @staticmethod
    def _require_object(
        values,
        record_name,
        position,
    ):
        if not isinstance(values, dict):
            raise ValueError(
                "%s snapshot record %d "
                "must be an object"
                % (
                    record_name,
                    position,
                )
            )

    @staticmethod
    def _required_int(
        values,
        name,
        record_name,
        position,
    ):
        if name not in values:
            raise ValueError(
                "%s snapshot record %d is "
                "missing %s"
                % (
                    record_name,
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
                "%s snapshot record %d field "
                "%s must be an integer"
                % (
                    record_name,
                    position,
                    name,
                )
            )

        return value

    @staticmethod
    def _required_string(
        values,
        name,
        record_name,
        position,
    ):
        if name not in values:
            raise ValueError(
                "%s snapshot record %d is "
                "missing %s"
                % (
                    record_name,
                    position,
                    name,
                )
            )

        value = values[name]

        if not isinstance(value, str):
            raise ValueError(
                "%s snapshot record %d field "
                "%s must be a string"
                % (
                    record_name,
                    position,
                    name,
                )
            )

        return value

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
