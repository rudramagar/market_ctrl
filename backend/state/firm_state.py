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
            "state_sequence": self.state_sequence,
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
            return self._apply_firm_status(message)

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

    def clear(self):
        with self._lock:
            self._firms.clear()

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
            state_sequence = 0
            state_timestamp_ns = 0

            if (
                current is not None
                and current.state_sequence > sequence
            ):
                state = current.state
                state_sequence = (
                    current.state_sequence
                )
                state_timestamp_ns = (
                    current.state_timestamp_ns
                )

            self._firms[message.firm_id] = FirmRecord(
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

            if (
                current is not None
                and sequence
                <= current.state_sequence
            ):
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

            self._firms[message.firm_id] = FirmRecord(
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
                    current.definition_timestamp_ns
                ),
                state_sequence=sequence,
                state_timestamp_ns=timestamp_ns,
            )

            return True
