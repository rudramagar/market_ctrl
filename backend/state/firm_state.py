from dataclasses import dataclass
from threading import RLock
from typing import Optional

from backend.protocol.drop.messages import (
    FirmMessage,
    FirmStatusMessage,
)


@dataclass(frozen=True)
class FirmRecord:
    """Current reconstructed state of one firm."""

    firm_index: Optional[int]
    firm_id: int
    firm_code: Optional[str]
    psms_code: Optional[str]
    firm_name: Optional[str]
    firm_type: Optional[str]
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
            "firm_index": self.firm_index,
            "firm_id": self.firm_id,
            "firm_code": self.firm_code,
            "psms_code": self.psms_code,
            "firm_name": self.firm_name,
            "firm_type": self.firm_type,
            "state": self.state,
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
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": (
                self.last_timestamp_ns
            ),
        }


class FirmStateStore:
    """Thread-safe in-memory firm state store."""

    def __init__(self):
        self._firms = {}
        self._lock = RLock()

    @property
    def count(self):
        with self._lock:
            return len(self._firms)

    def apply(self, message):
        if isinstance(message, FirmMessage):
            return self._apply_firm(message)

        if isinstance(message, FirmStatusMessage):
            return self._apply_firm_status(
                message
            )

        return False

    def get_firm(self, firm_id):
        firm_id = int(firm_id)

        with self._lock:
            return self._firms.get(firm_id)

    def get_firms(self):
        with self._lock:
            return tuple(
                sorted(
                    self._firms.values(),
                    key=lambda firm: firm.firm_id,
                )
            )

    def snapshot(self):
        return [
            firm.to_dict()
            for firm in self.get_firms()
        ]

    def restore(self, records):
        """
        Replace the current firm state from a snapshot.

        All records are validated before the live
        state is changed.
        """

        if not isinstance(records, list):
            raise ValueError(
                "firm snapshot must be a list"
            )

        restored_firms = {}

        for position, values in enumerate(records):
            if not isinstance(values, dict):
                raise ValueError(
                    "firm snapshot record %d "
                    "must be an object"
                    % position
                )

            record = self._restore_record(
                values,
                position,
            )

            if record.firm_id in restored_firms:
                raise ValueError(
                    "duplicate firm ID in snapshot: %d"
                    % record.firm_id
                )

            restored_firms[
                record.firm_id
            ] = record

        with self._lock:
            self._firms = restored_firms

        return len(restored_firms)

    def clear(self):
        with self._lock:
            self._firms.clear()

    @classmethod
    def _restore_record(
        cls,
        values,
        position,
    ):
        firm_id = cls._required_int(
            values,
            "firm_id",
            position,
        )

        if firm_id <= 0:
            raise ValueError(
                "firm snapshot record %d has "
                "invalid firm_id: %d"
                % (
                    position,
                    firm_id,
                )
            )

        definition_sequence = (
            cls._required_int(
                values,
                "definition_sequence",
                position,
            )
        )
        state_sequence = cls._required_int(
            values,
            "state_sequence",
            position,
        )
        definition_timestamp_ns = (
            cls._required_int(
                values,
                "definition_timestamp_ns",
                position,
            )
        )
        state_timestamp_ns = (
            cls._required_int(
                values,
                "state_timestamp_ns",
                position,
            )
        )

        if (
            definition_sequence < 0
            or state_sequence < 0
            or definition_timestamp_ns < 0
            or state_timestamp_ns < 0
        ):
            raise ValueError(
                "firm snapshot record %d has "
                "a negative sequence or timestamp"
                % position
            )

        return FirmRecord(
            firm_index=cls._optional_int(
                values,
                "firm_index",
                position,
            ),
            firm_id=firm_id,
            firm_code=cls._optional_string(
                values,
                "firm_code",
                position,
            ),
            psms_code=cls._optional_string(
                values,
                "psms_code",
                position,
            ),
            firm_name=cls._optional_string(
                values,
                "firm_name",
                position,
            ),
            firm_type=cls._optional_string(
                values,
                "firm_type",
                position,
            ),
            state=cls._optional_string(
                values,
                "state",
                position,
            ),
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
        )

    @staticmethod
    def _required_int(
        values,
        name,
        position,
    ):
        if name not in values:
            raise ValueError(
                "firm snapshot record %d is "
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
                "firm snapshot record %d field "
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
                "firm snapshot record %d field "
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
                "firm snapshot record %d field "
                "%s must be a string or null"
                % (
                    position,
                    name,
                )
            )

        return value

    def _apply_firm(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._firms.get(
                message.firm_id
            )

            if (
                current is not None
                and sequence
                <= current.definition_sequence
            ):
                return False

            state = message.state
            state_sequence = sequence
            state_timestamp_ns = timestamp_ns

            if (
                current is not None
                and current.state_sequence
                >= sequence
            ):
                state = current.state
                state_sequence = (
                    current.state_sequence
                )
                state_timestamp_ns = (
                    current.state_timestamp_ns
                )

            self._firms[message.firm_id] = (
                FirmRecord(
                    firm_index=message.firm_index,
                    firm_id=message.firm_id,
                    firm_code=message.firm_code,
                    psms_code=message.psms_code,
                    firm_name=message.firm_name,
                    firm_type=message.firm_type,
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

    def _apply_firm_status(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._firms.get(
                message.firm_id
            )

            if current is not None:
                latest_state_sequence = max(
                    current.definition_sequence,
                    current.state_sequence,
                )

                if sequence <= latest_state_sequence:
                    return False

            if current is None:
                self._firms[message.firm_id] = (
                    FirmRecord(
                        firm_index=(
                            message.firm_index
                        ),
                        firm_id=message.firm_id,
                        firm_code=None,
                        psms_code=None,
                        firm_name=None,
                        firm_type=None,
                        state=message.state,
                        definition_sequence=0,
                        definition_timestamp_ns=0,
                        state_sequence=sequence,
                        state_timestamp_ns=(
                            timestamp_ns
                        ),
                    )
                )

                return True

            self._firms[message.firm_id] = (
                FirmRecord(
                    firm_index=current.firm_index,
                    firm_id=current.firm_id,
                    firm_code=current.firm_code,
                    psms_code=current.psms_code,
                    firm_name=current.firm_name,
                    firm_type=current.firm_type,
                    state=message.state,
                    definition_sequence=(
                        current.definition_sequence
                    ),
                    definition_timestamp_ns=(
                        current
                        .definition_timestamp_ns
                    ),
                    state_sequence=sequence,
                    state_timestamp_ns=(
                        timestamp_ns
                    ),
                )
            )

            return True
