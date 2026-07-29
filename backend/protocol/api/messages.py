from enum import Enum, IntEnum

class ApiMessageType(IntEnum):
    ACCEPT_RESPONSE = 0
    REJECT_RESPONSE = 8
    UPDATE_USER_STATE_REQUEST = 29

class UserState(str, Enum):
    ACTIVE = "A"
    SUSPENDED = "S"

class FirmState(str, Enum):
    ACTIVE = "A"
    SUSPENDED = "S"
