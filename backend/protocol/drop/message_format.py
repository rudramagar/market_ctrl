import json
from pathlib import Path

from backend.protocol.drop.messages import (
    FirmMessage,
    FirmStatusMessage,
    MarketMessage,
    MercuryHeader,
    SbeHeader,
    UserMessage,
    UserStatusMessage,
)
from backend.protocol.errors import DropFormatError

SBE_HEADER_SIZE = 8

DEFAULT_SPEC_PATH = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "soup_drop_spec.json"
)


MESSAGE_CLASSES = {
    1: UserMessage,
    3: MarketMessage,
    4: FirmMessage,
    20: FirmStatusMessage,
    21: UserStatusMessage,
}


class DropMessageDecoder:
    """Decode fixed-length DROP SBE messages."""

    def __init__(self, spec_path=DEFAULT_SPEC_PATH):
        self.spec_path = Path(spec_path)
        self.byte_order = "little"
        self.schema_id = 0
        self.version = 0
        self.header_fields = []
        self.header_length = 0
        self.message_definitions = {}

        self._load_spec()

    def decode(self, payload):
        sbe_header, mercury_header = self._decode_headers(
            payload
        )

        definition = self._get_definition(
            sbe_header.template_id
        )
        message_class = self._get_message_class(
            sbe_header.template_id
        )

        self._validate_message_length(
            payload=payload,
            sbe_header=sbe_header,
            definition=definition,
        )

        values, final_offset = self._decode_fields(
            payload=payload,
            fields=definition["fields"],
            offset=self.header_length,
        )

        expected_length = definition["total_length"]

        if final_offset != expected_length:
            raise DropFormatError(
                "template %d ended at offset %d, expected %d"
                % (
                    sbe_header.template_id,
                    final_offset,
                    expected_length,
                )
            )

        return message_class(
            sbe_header=sbe_header,
            mercury_header=mercury_header,
            **values
        )

    def get_template_id(self, payload):
        if len(payload) < SBE_HEADER_SIZE:
            raise DropFormatError(
                "SBE header requires %d bytes, received %d"
                % (
                    SBE_HEADER_SIZE,
                    len(payload),
                )
            )

        return int.from_bytes(
            payload[2:4],
            byteorder=self.byte_order,
            signed=False,
        )

    def supports(self, payload):
        template_id = self.get_template_id(payload)

        return (
            str(template_id) in self.message_definitions
            and template_id in MESSAGE_CLASSES
        )

    def _decode_headers(self, payload):
        if len(payload) < self.header_length:
            raise DropFormatError(
                "DROP header requires %d bytes, received %d"
                % (
                    self.header_length,
                    len(payload),
                )
            )

        values, final_offset = self._decode_fields(
            payload=payload,
            fields=self.header_fields,
            offset=0,
        )

        if final_offset != self.header_length:
            raise DropFormatError(
                "invalid DROP common header length"
            )

        sbe_header = SbeHeader(
            block_length=values["block_length"],
            template_id=values["template_id"],
            schema_id=values["schema_id"],
            version=values["version"],
        )

        if sbe_header.schema_id != self.schema_id:
            raise DropFormatError(
                "unexpected schema ID: expected %d, received %d"
                % (
                    self.schema_id,
                    sbe_header.schema_id,
                )
            )

        if sbe_header.version != self.version:
            raise DropFormatError(
                "unsupported schema version: "
                "expected %d, received %d"
                % (
                    self.version,
                    sbe_header.version,
                )
            )

        mercury_header = MercuryHeader(
            timestamp_nanoseconds=values["timestamp_ns"],
            matching_engine_sequence=values[
                "matching_engine_seq_num"
            ],
        )

        return sbe_header, mercury_header

    def _decode_fields(self, payload, fields, offset):
        values = {}

        for field in fields:
            field_length = field["length"]
            end_offset = offset + field_length

            if end_offset > len(payload):
                raise DropFormatError(
                    "truncated field %s at offset %d"
                    % (
                        field["name"],
                        offset,
                    )
                )

            field_data = payload[offset:end_offset]

            values[field["name"]] = self._decode_field(
                field,
                field_data,
            )

            offset = end_offset

        return values, offset

    def _decode_field(self, field, field_data):
        field_name = field["name"]
        field_type = field["type"]

        if field_type == "int":
            value = int.from_bytes(
                field_data,
                byteorder=self.byte_order,
                signed=True,
            )

        elif field_type == "uint":
            value = int.from_bytes(
                field_data,
                byteorder=self.byte_order,
                signed=False,
            )

        elif field_type == "alpha":
            value = self._decode_text(
                field_data,
                field_name,
            )

        elif field_type == "bool_int":
            value = self._decode_int_boolean(
                field_data,
                field_name,
            )

        elif field_type == "bool_alpha":
            value = self._decode_alpha_boolean(
                field_data,
                field_name,
            )

        else:
            raise DropFormatError(
                "unsupported field type: %s"
                % field_type
            )

        allowed_values = field.get("allowed_values")

        if (
            allowed_values is not None
            and value not in allowed_values
        ):
            raise DropFormatError(
                "invalid value for %s: %r"
                % (
                    field_name,
                    value,
                )
            )

        return value

    def _decode_int_boolean(
        self,
        field_data,
        field_name,
    ):
        value = int.from_bytes(
            field_data,
            byteorder=self.byte_order,
            signed=True,
        )

        if value not in (0, 1):
            raise DropFormatError(
                "invalid boolean value for %s: %d"
                % (
                    field_name,
                    value,
                )
            )

        return bool(value)

    def _decode_alpha_boolean(
        self,
        field_data,
        field_name,
    ):
        value = self._decode_text(
            field_data,
            field_name,
        )

        if value not in ("F", "T"):
            raise DropFormatError(
                "invalid boolean value for %s: %r"
                % (
                    field_name,
                    value,
                )
            )

        return value == "T"

    def _validate_message_length(
        self,
        payload,
        sbe_header,
        definition,
    ):
        expected_length = definition["total_length"]
        expected_block_length = (
            expected_length - SBE_HEADER_SIZE
        )

        if sbe_header.block_length != expected_block_length:
            raise DropFormatError(
                "invalid block length for template %d: "
                "expected %d, received %d"
                % (
                    sbe_header.template_id,
                    expected_block_length,
                    sbe_header.block_length,
                )
            )

        if len(payload) != expected_length:
            raise DropFormatError(
                "invalid payload length for template %d: "
                "expected %d, received %d"
                % (
                    sbe_header.template_id,
                    expected_length,
                    len(payload),
                )
            )

    def _get_definition(self, template_id):
        definition = self.message_definitions.get(
            str(template_id)
        )

        if definition is None:
            raise DropFormatError(
                "unknown DROP template: %d"
                % template_id
            )

        return definition

    @staticmethod
    def _get_message_class(template_id):
        message_class = MESSAGE_CLASSES.get(template_id)

        if message_class is None:
            raise DropFormatError(
                "unsupported DROP template: %d"
                % template_id
            )

        return message_class

    def _load_spec(self):
        try:
            with self.spec_path.open(
                "r",
                encoding="utf-8",
            ) as spec_file:
                spec = json.load(spec_file)

        except (OSError, ValueError) as exc:
            raise DropFormatError(
                "failed to load DROP specification: %s"
                % exc
            ) from exc

        byte_order = spec.get("byte_order")
        common_header = spec.get("common_header", {})
        header_fields = common_header.get("fields")
        message_definitions = spec.get("messages")

        if byte_order not in ("little", "big"):
            raise DropFormatError(
                "invalid DROP byte order: %r"
                % byte_order
            )

        if not header_fields:
            raise DropFormatError(
                "DROP common header fields are missing"
            )

        if not message_definitions:
            raise DropFormatError(
                "DROP message definitions are missing"
            )

        self.byte_order = byte_order
        self.schema_id = int(spec["schema_id"])
        self.version = int(spec["version"])
        self.header_fields = header_fields
        self.header_length = sum(
            field["length"]
            for field in header_fields
        )
        self.message_definitions = message_definitions

        configured_header_length = common_header.get(
            "total_length"
        )

        if (
            configured_header_length is not None
            and configured_header_length
            != self.header_length
        ):
            raise DropFormatError(
                "common header length mismatch: "
                "configured %d, calculated %d"
                % (
                    configured_header_length,
                    self.header_length,
                )
            )

        self._validate_definitions()

    def _validate_definitions(self):
        for template_id, definition in (
            self.message_definitions.items()
        ):
            fields = definition.get("fields")
            total_length = definition.get("total_length")

            if not fields:
                raise DropFormatError(
                    "template %s has no fields"
                    % template_id
                )

            if not isinstance(total_length, int):
                raise DropFormatError(
                    "template %s has invalid total length"
                    % template_id
                )

            calculated_length = (
                self.header_length
                + sum(
                    field["length"]
                    for field in fields
                )
            )

            if calculated_length != total_length:
                raise DropFormatError(
                    "template %s length mismatch: "
                    "configured %d, calculated %d"
                    % (
                        template_id,
                        total_length,
                        calculated_length,
                    )
                )

    @staticmethod
    def _decode_text(field_data, field_name):
        try:
            return field_data.decode("ascii").rstrip(
                " \x00"
            )
        except UnicodeDecodeError as exc:
            raise DropFormatError(
                "invalid ASCII value for %s"
                % field_name
            ) from exc
