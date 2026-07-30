from enum import Enum, IntEnum

class ApiMessageType(IntEnum):
    ACCEPT_RESPONSE = 0
    REJECT_RESPONSE = 8
    UPDATE_MARKET_STATE_REQUEST = 20
    UPDATE_FIRM_STATE_REQUEST = 21
    UPDATE_USER_STATE_REQUEST = 29

class UserState(str, Enum):
    ACTIVE = "A"
    SUSPENDED = "S"

class FirmState(str, Enum):
    ACTIVE = "A"
    SUSPENDED = "S"

class MarketState:
    ACTIVE = "A"
    SUSPENDED = "S"

    @classmethod
    def validate(cls, state):
        if state not in (
            cls.ACTIVE,
            cls.SUSPENDED,
        ):
            raise ValueError(
                "invalid market state: %r"
                % state
            )

        return state
