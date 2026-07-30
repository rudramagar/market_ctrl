from dataclasses import dataclass
from threading import RLock
from typing import Optional

from backend.protocol.drop.messages import (
    UserMessage,
    UserStatusMessage,
)


@dataclass(frozen=True)
class UserRecord:
    """Current reconstructed state of one user."""

    user_index: Optional[int]
    user_id: int
    user_name: Optional[str]
    liquidity_provider: Optional[bool]
    state: Optional[str]

    firm_index: Optional[int]
    firm_id: Optional[int]
    executing_firm: Optional[str]
    capacity: Optional[str]
    clearing_firm: Optional[str]
    clearing_ref: Optional[str]
    allow_override: Optional[bool]
    live_order_limit: Optional[int]
    user_type_id: Optional[int]

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
            "user_index": self.user_index,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "liquidity_provider": (
                self.liquidity_provider
            ),
            "state": self.state,
            "firm_index": self.firm_index,
            "firm_id": self.firm_id,
            "executing_firm": self.executing_firm,
            "capacity": self.capacity,
            "clearing_firm": self.clearing_firm,
            "clearing_ref": self.clearing_ref,
            "allow_override": self.allow_override,
            "live_order_limit": (
                self.live_order_limit
            ),
            "user_type_id": self.user_type_id,
            "definition_sequence": (
                self.definition_sequence
            ),
            "state_sequence": self.state_sequence,
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": (
                self.last_timestamp_ns
            ),
        }


class UserStateStore:
    """Thread-safe in-memory user state store."""

    def __init__(self):
        self._users = {}
        self._lock = RLock()

    @property
    def count(self):
        with self._lock:
            return len(self._users)

    def apply(self, message):
        if isinstance(message, UserMessage):
            return self._apply_user(message)

        if isinstance(message, UserStatusMessage):
            return self._apply_user_status(message)

        return False

    def get_user(self, user_id):
        user_id = int(user_id)

        with self._lock:
            return self._users.get(user_id)

    def get_users(self):
        with self._lock:
            return tuple(
                sorted(
                    self._users.values(),
                    key=lambda user: user.user_id,
                )
            )

    def snapshot(self):
        return [
            user.to_dict()
            for user in self.get_users()
        ]

    def clear(self):
        with self._lock:
            self._users.clear()

    def _apply_user(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._users.get(
                message.user_id
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

            self._users[message.user_id] = UserRecord(
                user_index=message.user_index,
                user_id=message.user_id,
                user_name=message.user_name,
                liquidity_provider=(
                    message.liquidity_provider
                ),
                state=state,
                firm_index=message.firm_index,
                firm_id=message.firm_id,
                executing_firm=(
                    message.executing_firm
                ),
                capacity=message.capacity,
                clearing_firm=(
                    message.clearing_firm
                ),
                clearing_ref=message.clearing_ref,
                allow_override=(
                    message.allow_override
                ),
                live_order_limit=(
                    message.live_order_limit
                ),
                user_type_id=message.user_type_id,
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

    def _apply_user_status(self, message):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._users.get(
                message.user_id
            )

            if (
                current is not None
                and sequence
                <= current.state_sequence
            ):
                return False

            if current is None:
                self._users[message.user_id] = (
                    UserRecord(
                        user_index=(
                            message.user_index
                        ),
                        user_id=message.user_id,
                        user_name=None,
                        liquidity_provider=None,
                        state=message.state,
                        firm_index=None,
                        firm_id=None,
                        executing_firm=None,
                        capacity=None,
                        clearing_firm=None,
                        clearing_ref=None,
                        allow_override=None,
                        live_order_limit=None,
                        user_type_id=None,
                        definition_sequence=0,
                        definition_timestamp_ns=0,
                        state_sequence=sequence,
                        state_timestamp_ns=(
                            timestamp_ns
                        ),
                    )
                )

                return True

            self._users[message.user_id] = UserRecord(
                user_index=current.user_index,
                user_id=current.user_id,
                user_name=current.user_name,
                liquidity_provider=(
                    current.liquidity_provider
                ),
                state=message.state,
                firm_index=current.firm_index,
                firm_id=current.firm_id,
                executing_firm=(
                    current.executing_firm
                ),
                capacity=current.capacity,
                clearing_firm=(
                    current.clearing_firm
                ),
                clearing_ref=current.clearing_ref,
                allow_override=(
                    current.allow_override
                ),
                live_order_limit=(
                    current.live_order_limit
                ),
                user_type_id=current.user_type_id,
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
