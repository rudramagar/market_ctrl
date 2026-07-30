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

    def apply(self, message):
        """Apply a decoded DROP message to the matching store."""

        if self.users.apply(message):
            return True

        if self.firms.apply(message):
            return True

        if self.markets.apply(message):
            return True

        return False

    def clear(self):
        self.users.clear()
        self.firms.clear()
        self.markets.clear()

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
