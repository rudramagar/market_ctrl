import struct

from backend.protocol.errors import SoupError
from backend.protocol.soup.messages import (
    SoupLoginAccepted,
    SoupPacket,
)


SOUP_HEADER_SIZE = 2
MAX_SOUP_PACKET_SIZE = 65535


def encode_packet(packet_type, payload=b""):
    if len(packet_type) != 1:
        raise ValueError("packet type must contain one character")

    try:
        packet_type_bytes = packet_type.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "packet type must be ASCII"
        ) from exc

    body = packet_type_bytes + payload

    if len(body) > MAX_SOUP_PACKET_SIZE:
        raise ValueError("Soup packet is too large")

    return struct.pack(">H", len(body)) + body


def decode_packet(body):
    if not body:
        raise SoupError("Soup packet body is empty")

    try:
        packet_type = body[:1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise SoupError(
            "invalid Soup packet type"
        ) from exc

    return SoupPacket(
        packet_type=packet_type,
        payload=body[1:],
    )


def encode_login_request(
    username,
    password,
    session="",
    sequence=1,
):
    payload = (
        _encode_text(username, 6, "username")
        + _encode_text(password, 10, "password")
        + _encode_text(session, 10, "session")
        + _encode_sequence(sequence)
    )

    return encode_packet("L", payload)


def decode_login_accepted(payload):
    expected_size = 30

    if len(payload) != expected_size:
        raise SoupError(
            "invalid login accepted length: expected %d, received %d"
            % (expected_size, len(payload))
        )

    session = _decode_text(payload[:10])
    sequence_text = payload[10:30].decode("ascii").strip()

    try:
        sequence = int(sequence_text)
    except ValueError as exc:
        raise SoupError(
            "invalid login sequence: %r" % sequence_text
        ) from exc

    return SoupLoginAccepted(
        session=session,
        sequence=sequence,
    )


def decode_login_rejected(payload):
    if len(payload) != 1:
        raise SoupError(
            "invalid login rejected length: %d"
            % len(payload)
        )

    return payload.decode("ascii")


def _encode_text(value, size, field_name):
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "%s must contain ASCII characters" % field_name
        ) from exc

    if len(encoded) > size:
        raise ValueError(
            "%s exceeds %d bytes" % (field_name, size)
        )

    return encoded.ljust(size, b" ")


def _encode_sequence(sequence):
    if sequence < 0:
        raise ValueError("sequence cannot be negative")

    encoded = str(sequence).encode("ascii")

    if len(encoded) > 20:
        raise ValueError("sequence exceeds 20 bytes")

    return encoded.rjust(20, b" ")


def _decode_text(value):
    return value.decode("ascii").rstrip(" \x00")
