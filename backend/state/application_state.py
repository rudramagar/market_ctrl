import time
from threading import Condition, RLock

from backend.state.firm_state import FirmStateStore
from backend.state.market_state import MarketStateStore
from backend.state.user_state import UserStateStore


class ApplicationState:
    """Current reconstructed application state."""

    def __init__(
        self,
        user_store=None,
        firm_store=None,
        market_store=None,
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

        self._condition = Condition(RLock())

    def apply(self, message):
        """Apply a decoded DROP message."""

        applied = False

        if self.users.apply(message):
            applied = True

        elif self.firms.apply(message):
            applied = True

        elif self.markets.apply(message):
            applied = True

        if applied:
            with self._condition:
                self._condition.notify_all()

        return applied

    def clear(self):
        self.users.clear()
        self.firms.clear()
        self.markets.clear()

        with self._condition:
            self._condition.notify_all()

    def snapshot(self):
        return {
            "users": self.users.snapshot(),
            "firms": self.firms.snapshot(),
            "markets": self.markets.snapshot(),
        }

    def counts(self):
        return {
            "users": self.users.count,
            "firms": self.firms.count,
            "markets": self.markets.count,
        }

    def wait_for_user(
        self,
        user_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: self.users.get_user(
                user_id
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_firm(
        self,
        firm_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: self.firms.get_firm(
                firm_id
            ),
            timeout_seconds=timeout_seconds,
        )

    def wait_for_market(
        self,
        market_id,
        timeout_seconds=None,
    ):
        return self._wait_for_record(
            getter=lambda: self.markets.get_market(
                market_id
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
            getter=lambda: self.users.get_user(
                user_id
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
            getter=lambda: self.firms.get_firm(
                firm_id
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
            getter=lambda: self.markets.get_market(
                market_id
            ),
            expected_state=expected_state,
            after_sequence=after_sequence,
            timeout_seconds=timeout_seconds,
        )

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

                remaining = self._get_remaining(
                    deadline
                )

                if remaining == 0:
                    return None

                self._condition.wait(remaining)

    def _wait_for_state(
        self,
        getter,
        expected_state,
        after_sequence,
        timeout_seconds,
    ):
        after_sequence = int(after_sequence)

        deadline = self._get_deadline(
            timeout_seconds
        )

        with self._condition:
            while True:
                record = getter()

                if (
                    record is not None
                    and record.state == expected_state
                    and record.last_sequence
                    > after_sequence
                ):
                    return record

                remaining = self._get_remaining(
                    deadline
                )

                if remaining == 0:
                    return None

                self._condition.wait(remaining)

    @staticmethod
    def _get_deadline(timeout_seconds):
        if timeout_seconds is None:
            return None

        timeout_seconds = float(
            timeout_seconds
        )

        if timeout_seconds < 0:
            raise ValueError(
                "timeout cannot be negative"
            )

        return time.monotonic() + timeout_seconds

    @staticmethod
    def _get_remaining(deadline):
        if deadline is None:
            return None

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            return 0

        return remaining
