import struct

from backend.protocol.drop.messages import (
    FirmMessage,
    FirmStatusMessage,
    MercuryHeader,
    SbeHeader,
    UserMessage,
    UserStatusMessage,
)
from backend.protocol.errors import DropFormatError

SBE_HEADER_SIZE = 8
MERCURY_HEADER_SIZE = 16
DROP_HEADER_SIZE = SBE_HEADER_SIZE + MERCURY_HEADER_SIZE

EXPECTED_SCHEMA_ID = 901
SUPPORTED_VERSION = 1

USER_TEMPLATE_ID = 1
USER_BLOCK_LENGTH = 100

MARKET_TEMPLATE_ID = 3
MARKET_BLOCK_LENGTH = 32

FIRM_TEMPLATE_ID = 4
FIRM_BLOCK_LENGTH = 102

FIRM_STATUS_TEMPLATE_ID = 20
FIRM_STATUS_BLOCK_LENGTH = 25

USER_STATUS_TEMPLATE_ID = 21
USER_STATUS_BLOCK_LENGTH = 25

def decode_sbe_header(payload):
    if len(payload) < SBE_HEADER_SIZE:
        raise DropFormatError(
            "SBE header requires %d bytes, received %d"
            % (SBE_HEADER_SIZE, len(payload))
        )

    values = struct.unpack_from("<HHHH", payload, 0)

    header = SbeHeader(
        block_length=values[0],
        template_id=values[1],
        schema_id=values[2],
        version=values[3],
    )

    if header.schema_id != EXPECTED_SCHEMA_ID:
        raise DropFormatError(
            "unexpected schema ID: %d"
            % header.schema_id
        )

    if header.version != SUPPORTED_VERSION:
        raise DropFormatError(
            "unsupported schema version: %d"
            % header.version
        )

    return header


def decode_mercury_header(payload):
    if len(payload) < DROP_HEADER_SIZE:
        raise DropFormatError(
            "DROP header requires %d bytes, received %d"
            % (DROP_HEADER_SIZE, len(payload))
        )

    timestamp_nanoseconds, matching_engine_sequence = (
        struct.unpack_from(
            "<qq",
            payload,
            SBE_HEADER_SIZE,
        )
    )

    return MercuryHeader(
        timestamp_nanoseconds=timestamp_nanoseconds,
        matching_engine_sequence=matching_engine_sequence,
    )


def decode_headers(payload):
    sbe_header = decode_sbe_header(payload)
    mercury_header = decode_mercury_header(payload)

    expected_length = (
        SBE_HEADER_SIZE
        + sbe_header.block_length
    )

    if len(payload) < expected_length:
        raise DropFormatError(
            "truncated DROP message: expected at least %d bytes, "
            "received %d"
            % (expected_length, len(payload))
        )

    return sbe_header, mercury_header


def decode_user_message(payload):
    sbe_header, mercury_header = decode_headers(payload)

    if sbe_header.template_id != USER_TEMPLATE_ID:
        raise DropFormatError(
            "expected User template %d, received %d"
            % (
                USER_TEMPLATE_ID,
                sbe_header.template_id,
            )
        )

    if sbe_header.block_length < USER_BLOCK_LENGTH:
        raise DropFormatError(
            "invalid User block length: expected at least %d, "
            "received %d"
            % (
                USER_BLOCK_LENGTH,
                sbe_header.block_length,
            )
        )

    liquidity_provider = struct.unpack_from(
        "<b",
        payload,
        64,
    )[0]

    if liquidity_provider not in (0, 1):
        raise DropFormatError(
            "invalid liquidity provider value: %d"
            % liquidity_provider
        )

    state = _decode_text(payload, 65, 1)

    if state not in ("A", "S", "D"):
        raise DropFormatError(
            "invalid user state: %r" % state
        )

    capacity = _decode_text(payload, 84, 1)

    if capacity not in ("A", "P"):
        raise DropFormatError(
            "invalid user capacity: %r" % capacity
        )

    allow_override = _decode_text(payload, 99, 1)

    if allow_override not in ("F", "T"):
        raise DropFormatError(
            "invalid allow override value: %r"
            % allow_override
        )

    return UserMessage(
        sbe_header=sbe_header,
        mercury_header=mercury_header,
        user_index=struct.unpack_from(
            "<i", payload, 24
        )[0],
        user_id=struct.unpack_from(
            "<i", payload, 28
        )[0],
        user_name=_decode_text(payload, 32, 32),
        liquidity_provider=bool(liquidity_provider),
        state=state,
        firm_index=struct.unpack_from(
            "<i", payload, 66
        )[0],
        firm_id=struct.unpack_from(
            "<i", payload, 70
        )[0],
        executing_firm=_decode_text(
            payload, 74, 10
        ),
        capacity=capacity,
        clearing_firm=_decode_text(
            payload, 85, 6
        ),
        clearing_ref=_decode_text(
            payload, 91, 8
        ),
        allow_override=allow_override == "T",
        live_order_limit=struct.unpack_from(
            "<i", payload, 100
        )[0],
        user_type_id=struct.unpack_from(
            "<i", payload, 104
        )[0],
    )


def _decode_text(payload, offset, length):
    field_data = payload[offset:offset + length]

    if len(field_data) != length:
        raise DropFormatError(
            "field at offset %d requires %d bytes"
            % (offset, length)
        )

    try:
        return field_data.decode("ascii").rstrip(
            " \x00"
        )
    except UnicodeDecodeError as exc:
        raise DropFormatError(
            "invalid ASCII field at offset %d"
            % offset
        ) from exc

def decode_user_status_message(payload):
    sbe_header, mercury_header = decode_headers(payload)

    if sbe_header.template_id != USER_STATUS_TEMPLATE_ID:
        raise DropFormatError(
            "expected UserStatus template %d, received %d"
            % (
                USER_STATUS_TEMPLATE_ID,
                sbe_header.template_id,
            )
        )

    if sbe_header.block_length < USER_STATUS_BLOCK_LENGTH:
        raise DropFormatError(
            "invalid UserStatus block length: "
            "expected at least %d, received %d"
            % (
                USER_STATUS_BLOCK_LENGTH,
                sbe_header.block_length,
            )
        )

    state = _decode_text(payload, 32, 1)

    if state not in ("A", "S", "D"):
        raise DropFormatError(
            "invalid user status: %r" % state
        )

    return UserStatusMessage(
        sbe_header=sbe_header,
        mercury_header=mercury_header,
        user_index=struct.unpack_from(
            "<i", payload, 24
        )[0],
        user_id=struct.unpack_from(
            "<i", payload, 28
        )[0],
        state=state,
    )

def decode_firm_message(payload):
    sbe_header, mercury_header = decode_headers(payload)

    if sbe_header.template_id != FIRM_TEMPLATE_ID:
        raise DropFormatError(
            "expected Firm template %d, received %d"
            % (
                FIRM_TEMPLATE_ID,
                sbe_header.template_id,
            )
        )

    if sbe_header.block_length < FIRM_BLOCK_LENGTH:
        raise DropFormatError(
            "invalid Firm block length: "
            "expected at least %d, received %d"
            % (
                FIRM_BLOCK_LENGTH,
                sbe_header.block_length,
            )
        )

    firm_type = _decode_text(payload, 108, 1)

    if firm_type not in ("I", "E", "B", "D"):
        raise DropFormatError(
            "invalid firm type: %r" % firm_type
        )

    state = _decode_text(payload, 109, 1)

    if state not in ("A", "S", "D"):
        raise DropFormatError(
            "invalid firm state: %r" % state
        )

    return FirmMessage(
        sbe_header=sbe_header,
        mercury_header=mercury_header,
        firm_index=struct.unpack_from(
            "<i", payload, 24
        )[0],
        firm_id=struct.unpack_from(
            "<i", payload, 28
        )[0],
        firm_code=_decode_text(
            payload, 32, 32
        ),
        psms_code=_decode_text(
            payload, 64, 12
        ),
        firm_name=_decode_text(
            payload, 76, 32
        ),
        firm_type=firm_type,
        state=state,
    )

def decode_firm_status_message(payload):
    sbe_header, mercury_header = decode_headers(payload)

    if sbe_header.template_id != FIRM_STATUS_TEMPLATE_ID:
        raise DropFormatError(
            "expected FirmStatus template %d, received %d"
            % (
                FIRM_STATUS_TEMPLATE_ID,
                sbe_header.template_id,
            )
        )

    if sbe_header.block_length < FIRM_STATUS_BLOCK_LENGTH:
        raise DropFormatError(
            "invalid FirmStatus block length: "
            "expected at least %d, received %d"
            % (
                FIRM_STATUS_BLOCK_LENGTH,
                sbe_header.block_length,
            )
        )

    state = _decode_text(payload, 32, 1)

    if state not in ("A", "S", "D"):
        raise DropFormatError(
            "invalid firm status: %r" % state
        )

    return FirmStatusMessage(
        sbe_header=sbe_header,
        mercury_header=mercury_header,
        firm_index=struct.unpack_from(
            "<i", payload, 24
        )[0],
        firm_id=struct.unpack_from(
            "<i", payload, 28
        )[0],
        state=state,
    )
