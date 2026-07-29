import json
from enum import Enum
from pathlib import Path

from backend.protocol.errors import ApiError


DEFAULT_SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "soup_api_spec.json"
)


class ApiMessageFormat:
    """Encode and decode API messages using the JSON specification."""

    def __init__(self, spec_path=DEFAULT_SPEC_PATH):
        self.spec_path = Path(spec_path)
        self.byte_order = "little"
        self.messages = {}
        self.reject_reasons = {}

        self._load_spec()

    def encode(self, message_type, values):
        message = self._get_message(message_type)
        payload = bytearray()

        for field in message["fields"]:
            field_name = field["name"]

            if field_name in values:
                value = values[field_name]
            elif "value" in field:
                value = field["value"]
            else:
                raise ApiError(
                    "missing API field: %s" % field_name
                )

            if "value" in field and value != field["value"]:
                raise ApiError(
                    "invalid value for %s: expected %r"
                    % (field_name, field["value"])
                )

            payload.extend(
                self._encode_field(field, value)
            )

        return bytes(payload)

    def decode(self, message_type, payload):
        message = self._get_message(message_type)
        expected_length = self.message_length(message_type)

        if len(payload) != expected_length:
            raise ApiError(
                "invalid API message length: expected %d, received %d"
                % (expected_length, len(payload))
            )

        values = {}
        offset = 0

        for field in message["fields"]:
            field_length = field["length"]
            field_data = payload[
                offset:offset + field_length
            ]

            value = self._decode_field(
                field,
                field_data,
            )

            if "value" in field and value != field["value"]:
                raise ApiError(
                    "invalid value for %s: expected %r, received %r"
                    % (
                        field["name"],
                        field["value"],
                        value,
                    )
                )

            values[field["name"]] = value
            offset += field_length

        return values

    def get_message_type(self, payload):
        if not payload:
            raise ApiError("API payload is empty")

        return payload[0]

    def message_length(self, message_type):
        message = self._get_message(message_type)

        return sum(
            field["length"]
            for field in message["fields"]
        )

    def get_reject_reason(self, reject_reason):
        return self.reject_reasons.get(
            str(reject_reason),
            "unknown_reject_reason",
        )

    def _load_spec(self):
        try:
            with self.spec_path.open(
                "r",
                encoding="utf-8",
            ) as spec_file:
                spec = json.load(spec_file)

        except (OSError, ValueError) as exc:
            raise ApiError(
                "failed to load API specification: %s"
                % exc
            ) from exc

        byte_order = spec.get("byte_order", "little")

        if byte_order not in ("little", "big"):
            raise ApiError(
                "invalid API byte order: %s"
                % byte_order
            )

        self.byte_order = byte_order
        self.messages = spec.get("messages", {})
        self.reject_reasons = spec.get(
            "reject_reasons",
            {},
        )

        if not self.messages:
            raise ApiError(
                "API specification contains no messages"
            )

    def _get_message(self, message_type):
        message_key = str(int(message_type))
        message = self.messages.get(message_key)

        if message is None:
            raise ApiError(
                "unsupported API message type: %s"
                % message_type
            )

        return message

    def _encode_field(self, field, value):
        field_type = field["type"]
        field_length = field["length"]

        if isinstance(value, Enum):
            value = value.value

        if field_type == "alpha":
            return self._encode_text(
                value,
                field_length,
                field["name"],
            )

        if field_type not in ("int", "uint"):
            raise ApiError(
                "unsupported API field type: %s"
                % field_type
            )

        try:
            return int(value).to_bytes(
                field_length,
                byteorder=self.byte_order,
                signed=field_type == "int",
            )
        except (OverflowError, TypeError, ValueError) as exc:
            raise ApiError(
                "invalid value for %s: %r"
                % (field["name"], value)
            ) from exc

    def _decode_field(self, field, field_data):
        field_type = field["type"]

        if field_type == "alpha":
            try:
                return field_data.decode("ascii").rstrip(
                    " \x00"
                )
            except UnicodeDecodeError as exc:
                raise ApiError(
                    "invalid ASCII data for %s"
                    % field["name"]
                ) from exc

        if field_type not in ("int", "uint"):
            raise ApiError(
                "unsupported API field type: %s"
                % field_type
            )

        return int.from_bytes(
            field_data,
            byteorder=self.byte_order,
            signed=field_type == "int",
        )

    @staticmethod
    def _encode_text(value, length, field_name):
        if not isinstance(value, str):
            raise ApiError(
                "%s must be a string" % field_name
            )

        try:
            encoded = value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ApiError(
                "%s must contain ASCII characters"
                % field_name
            ) from exc

        if len(encoded) > length:
            raise ApiError(
                "%s exceeds %d bytes"
                % (field_name, length)
            )

        return encoded.ljust(length, b" ")
