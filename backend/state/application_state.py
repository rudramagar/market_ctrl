import logging
import time
from threading import Condition, RLock

from backend.events.state_event import (
    EVENT_CREATED,
    EVENT_UPDATED,
    StateEvent,
)
from backend.events.state_event_bus import (
    StateEventBus,
    StateEventBusError,
)
from backend.protocol.drop.messages import (
    FirmMessage,
    FirmStatusMessage,
    MarketMessage,
    MarketTradingPhaseMessage,
    MarketTradingStateMessage,
    UserMessage,
    UserStatusMessage,
)
from backend.state.firm_state import (
    FirmStateStore,
)
from backend.state.market_state import (
    MarketStateStore,
)
from backend.state.reference_state import (
    ReferenceStateStore,
)
from backend.state.session_state import (
    SessionStateStore,
)
from backend.state.user_state import (
    UserStateStore,
)


logger = logging.getLogger(__name__)


USER_MESSAGE_TYPES = (
    UserMessage,
    UserStatusMessage,
)

FIRM_MESSAGE_TYPES = (
    FirmMessage,
    FirmStatusMessage,
)

MARKET_MESSAGE_TYPES = (
    MarketMessage,
    MarketTradingStateMessage,
    MarketTradingPhaseMessage,
)


class ApplicationState:
    """Current reconstructed application state."""

    def __init__(
        self,
        user_store=None,
        firm_store=None,
        market_store=None,
        reference_store=None,
        session_store=None,
        event_bus=None,
    ):
        self.users = (
            user_store
            if user_store is not None
            else UserStateStore()
        )

        self.firms = (
            firm_store
            if firm_store is not None
            else FirmStateStore()
        )

        self.markets = (
            market_store
            if market_store is not None
            else MarketStateStore()
        )

        self.references = (
            reference_store
            if reference_store is not None
            else ReferenceStateStore()
        )

        self.session = (
            session_store
            if session_store is not None
            else SessionStateStore()
        )

        if (
            event_bus is not None
            and not isinstance(
                event_bus,
                StateEventBus,
            )
        ):
            raise TypeError(
                "event bus must be a StateEventBus"
            )

        self.event_bus = (
            event_bus
            if event_bus is not None
            else StateEventBus()
        )

        self._condition = Condition(
            RLock()
        )

    def apply(self, message):
        """
        Apply one decoded DROP message.

        User, firm, and market updates publish one
        StateEvent after the state change succeeds.
        """

        with self._condition:
            event_target = (
                self._get_event_target(
                    message
                )
            )

            previous_record = None

            if event_target is not None:
                previous_record = (
                    event_target["getter"](
                        event_target["entity_id"]
                    )
                )

            applied = False

            if self.users.apply(message):
                applied = True

            elif self.firms.apply(message):
                applied = True

            elif self.markets.apply(message):
                applied = True

            elif self.references.apply(message):
                applied = True

            elif self.session.apply(message):
                applied = True

            if applied:
                if event_target is not None:
                    current_record = (
                        event_target["getter"](
                            event_target[
                                "entity_id"
                            ]
                        )
                    )

                    self._publish_state_event(
                        message=message,
                        entity_type=(
                            event_target[
                                "entity_type"
                            ]
                        ),
                        entity_id=(
                            event_target[
                                "entity_id"
                            ]
                        ),
                        previous_record=(
                            previous_record
                        ),
                        current_record=(
                            current_record
                        ),
                    )

                self._condition.notify_all()

            return applied

    def clear(self):
        """Clear all reconstructed application state."""

        with self._condition:
            self.users.clear()
            self.firms.clear()
            self.markets.clear()
            self.references.clear()
            self.session.clear()

            # Retained events refer to the old state.
            # Event IDs remain monotonic.
            self.event_bus.clear()

            self._condition.notify_all()

    def snapshot(self):
        """Return one consistent application snapshot."""

        with self._condition:
            return {
                "users": self.users.snapshot(),
                "firms": self.firms.snapshot(),
                "markets": (
                    self.markets.snapshot()
                ),
                "references": (
                    self.references.snapshot()
                ),
                "session": (
                    self.session.snapshot()
                ),
            }

    def restore(self, snapshot):
        """
        Restore a complete application snapshot.

        The snapshot is first validated using temporary
        stores. The live state is changed only after all
        sections pass validation.

        Restore does not publish live StateEvents.
        """

        if not isinstance(snapshot, dict):
            raise ValueError(
                "application snapshot must "
                "be an object"
            )

        required_sections = (
            "users",
            "firms",
            "markets",
            "references",
            "session",
        )

        for section_name in required_sections:
            if section_name not in snapshot:
                raise ValueError(
                    "application snapshot is missing %s"
                    % section_name
                )

        temporary_users = UserStateStore()
        temporary_firms = FirmStateStore()
        temporary_markets = (
            MarketStateStore()
        )
        temporary_references = (
            ReferenceStateStore()
        )
        temporary_session = (
            SessionStateStore()
        )

        # Validate all sections before changing
        # the live state.
        temporary_users.restore(
            snapshot["users"]
        )
        temporary_firms.restore(
            snapshot["firms"]
        )
        temporary_markets.restore(
            snapshot["markets"]
        )
        temporary_references.restore(
            snapshot["references"]
        )
        temporary_session.restore(
            snapshot["session"]
        )

        with self._condition:
            self.users.restore(
                snapshot["users"]
            )
            self.firms.restore(
                snapshot["firms"]
            )
            self.markets.restore(
                snapshot["markets"]
            )
            self.references.restore(
                snapshot["references"]
            )
            self.session.restore(
                snapshot["session"]
            )

            restored_counts = {
                "users": self.users.count,
                "firms": self.firms.count,
                "markets": self.markets.count,
                "user_types": (
                    self.references
                    .user_type_count
                ),
                "user_markets": (
                    self.references
                    .user_market_count
                ),
                "system_events": (
                    self.session.event_count
                ),
            }

            # Events from before the restore no
            # longer describe the current state.
            self.event_bus.clear()

            self._condition.notify_all()

            return restored_counts

    def counts(self):
        """Return current state record counts."""

        with self._condition:
            return {
                "users": self.users.count,
                "firms": self.firms.count,
                "markets": self.markets.count,
                "user_types": (
                    self.references
                    .user_type_count
                ),
                "user_markets": (
                    self.references
                    .user_market_count
                ),
                "system_events": (
                    self.session.event_count
                ),
            }

    def wait_for_user(
        self,
        user_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: (
                self.users.get_user(
                    user_id
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_firm(
        self,
        firm_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: (
                self.firms.get_firm(
                    firm_id
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_market(
        self,
        market_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: (
                self.markets.get_market(
                    market_id
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_user_type(
        self,
        user_type_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: (
                self.references
                .get_user_type(
                    user_type_id
                )
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_session(
        self,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: (
                self.session.trading_engine
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_user_state(
        self,
        user_id,
        expected_state,
        after_sequence=0,
        timeout_seconds=None,
    ):
        return self._wait_for_state(
            getter=lambda: (
                self.users.get_user(
                    user_id
                )
            ),
            expected_state=expected_state,
            after_sequence=after_sequence,
            timeout_seconds=timeout_seconds,
        )

    def wait_for_firm_state(
        self,
        firm_id,
        expected_state,
        after_sequence=0,
        timeout_seconds=None,
    ):
        return self._wait_for_state(
            getter=lambda: (
                self.firms.get_firm(
                    firm_id
                )
            ),
            expected_state=expected_state,
            after_sequence=after_sequence,
            timeout_seconds=timeout_seconds,
        )

    def wait_for_market_state(
        self,
        market_id,
        expected_state,
        after_sequence=0,
        timeout_seconds=None,
    ):
        return self._wait_for_state(
            getter=lambda: (
                self.markets.get_market(
                    market_id
                )
            ),
            expected_state=expected_state,
            after_sequence=after_sequence,
            timeout_seconds=timeout_seconds,
        )

    def wait_for_end_session(
        self,
        timeout_seconds=None,
    ):
        deadline = self._get_deadline(
            timeout_seconds
        )

        with self._condition:
            while True:
                if (
                    self.session
                    .end_session_dispatched
                ):
                    return True

                remaining = (
                    self._get_remaining(
                        deadline
                    )
                )

                if remaining == 0:
                    return False

                self._condition.wait(
                    remaining
                )

    def _get_event_target(
        self,
        message,
    ):
        if isinstance(
            message,
            USER_MESSAGE_TYPES,
        ):
            return {
                "entity_type": "user",
                "entity_id": message.user_id,
                "getter": self.users.get_user,
            }

        if isinstance(
            message,
            FIRM_MESSAGE_TYPES,
        ):
            return {
                "entity_type": "firm",
                "entity_id": message.firm_id,
                "getter": self.firms.get_firm,
            }

        if isinstance(
            message,
            MARKET_MESSAGE_TYPES,
        ):
            return {
                "entity_type": "market",
                "entity_id": message.market_id,
                "getter": (
                    self.markets.get_market
                ),
            }

        return None

    def _publish_state_event(
        self,
        message,
        entity_type,
        entity_id,
        previous_record,
        current_record,
    ):
        if current_record is None:
            return

        previous_values = (
            previous_record.to_dict()
            if previous_record is not None
            else None
        )

        current_values = (
            current_record.to_dict()
        )

        if previous_values is None:
            event_type = EVENT_CREATED

        else:
            event_type = EVENT_UPDATED

        changed_fields = (
            self._get_changed_fields(
                previous_values,
                current_values,
            )
        )

        mercury_header = (
            message.mercury_header
        )

        event = StateEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            sequence=(
                mercury_header
                .matching_engine_sequence
            ),
            timestamp_ns=(
                mercury_header
                .timestamp_nanoseconds
            ),
            message_type=(
                type(message).__name__
            ),
            record=current_values,
            changed_fields=changed_fields,
        )

        try:
            self.event_bus.publish(
                event
            )

        except StateEventBusError:
            # State reconstruction must continue
            # even if the live event stream is closed.
            logger.exception(
                "failed to publish state event: "
                "entity_type=%s entity_id=%r",
                entity_type,
                entity_id,
            )

    @staticmethod
    def _get_changed_fields(
        previous_values,
        current_values,
    ):
        if previous_values is None:
            return {
                field_name: {
                    "old": None,
                    "new": current_values[
                        field_name
                    ],
                }
                for field_name in sorted(
                    current_values
                )
            }

        changed_fields = {}

        field_names = set(
            previous_values
        )
        field_names.update(
            current_values
        )

        for field_name in sorted(
            field_names
        ):
            old_value = (
                previous_values.get(
                    field_name
                )
            )
            new_value = (
                current_values.get(
                    field_name
                )
            )

            if old_value == new_value:
                continue

            changed_fields[field_name] = {
                "old": old_value,
                "new": new_value,
            }

        return changed_fields

    def _wait_for_record(
        self,
        getter,
        timeout_seconds,
    ):
        deadline = self._get_deadline(
            timeout_seconds
        )

        with self._condition:
            while True:
                record = getter()

                if record is not None:
                    return record

                remaining = (
                    self._get_remaining(
                        deadline
                    )
                )

                if remaining == 0:
                    return None

                self._condition.wait(
                    remaining
                )

    def _wait_for_state(
        self,
        getter,
        expected_state,
        after_sequence,
        timeout_seconds,
    ):
        after_sequence = int(
            after_sequence
        )

        deadline = self._get_deadline(
            timeout_seconds
        )

        with self._condition:
            while True:
                record = getter()

                if (
                    record is not None
                    and record.state
                    == expected_state
                    and record.state_sequence
                    > after_sequence
                ):
                    return record

                remaining = (
                    self._get_remaining(
                        deadline
                    )
                )

                if remaining == 0:
                    return None

                self._condition.wait(
                    remaining
                )

    @staticmethod
    def _get_deadline(
        timeout_seconds,
    ):
        if timeout_seconds is None:
            return None

        timeout_seconds = float(
            timeout_seconds
        )

        if timeout_seconds < 0:
            raise ValueError(
                "timeout cannot be negative"
            )

        return (
            time.monotonic()
            + timeout_seconds
        )

    @staticmethod
    def _get_remaining(
        deadline,
    ):
        if deadline is None:
            return None

        remaining = (
            deadline
            - time.monotonic()
        )

        if remaining <= 0:
            return 0

        return remaining
