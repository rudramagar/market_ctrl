#!/usr/bin/env python3

from backend.protocol.api.message_format import ApiMessageFormat
from backend.protocol.api.messages import (
    ApiMessageType,
    UserState,
)


def test_update_user_state(message_format):
    payload = message_format.encode(
        ApiMessageType.UPDATE_USER_STATE_REQUEST,
        {
            "correlation_id": 1001,
            "user_id": 402,
            "suspension_status": UserState.SUSPENDED,
        },
    )

    assert len(payload) == 14
    assert payload[0] == 29

    print("update user state:")
    print("  length:", len(payload))
    print("  payload:", payload.hex())


def test_accept_response(message_format):
    payload = bytes.fromhex(
        "00"
        "e903000000000000"
    )

    message_type = message_format.get_message_type(payload)
    response = message_format.decode(
        message_type,
        payload,
    )

    assert response["msg_type"] == 0
    assert response["correlation_id"] == 1001

    print("accept response:")
    print(" ", response)


def test_reject_response(message_format):
    payload = bytes.fromhex(
        "08"
        "e903000000000000"
        "0800"
    )

    message_type = message_format.get_message_type(payload)
    response = message_format.decode(
        message_type,
        payload,
    )

    assert response["msg_type"] == 8
    assert response["correlation_id"] == 1001
    assert response["reject_reason"] == 8

    reason = message_format.get_reject_reason(
        response["reject_reason"]
    )

    print("reject response:")
    print(" ", response)
    print("  reason:", reason)


def main():
    message_format = ApiMessageFormat()

    test_update_user_state(message_format)
    test_accept_response(message_format)
    test_reject_response(message_format)

    print("API message format tests passed")


if __name__ == "__main__":
    main()
