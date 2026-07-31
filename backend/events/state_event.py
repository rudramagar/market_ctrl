import copy
import time


EVENT_CREATED = "created"
EVENT_UPDATED = "updated"
EVENT_DELETED = "deleted"

VALID_EVENT_TYPES = (
    EVENT_CREATED,
    EVENT_UPDATED,
    EVENT_DELETED,
)


class StateEvent:
    """
    Describe one change applied to ApplicationState.

    The event contains the latest entity snapshot and
    the fields that changed. It does not modify the
    underlying application state.
    """

    __slots__ = (
        "_event_type",
        "_entity_type",
        "_entity_id",
        "_sequence",
        "_timestamp_ns",
        "_message_type",
        "_record",
        "_changed_fields",
    )

    def __init__(
        self,
        event_type,
        entity_type,
        entity_id,
        sequence,
        record,
        changed_fields=None,
        message_type=None,
        timestamp_ns=None,
    ):
        self._event_type = self._validate_event_type(
            event_type
        )

        self._entity_type = self._validate_text(
            entity_type,
            "entity type",
        )

        self._entity_id = self._validate_entity_id(
            entity_id
        )

        self._sequence = self._validate_sequence(
            sequence
        )

        self._record = self._validate_record(
            record
        )

        self._changed_fields = (
            self._validate_changed_fields(
                changed_fields
            )
        )

        self._message_type = (
            self._validate_optional_text(
                message_type,
                "message type",
            )
        )

        if timestamp_ns is None:
            timestamp_ns = int(
                time.time() * 1000000000
            )

        self._timestamp_ns = (
            self._validate_timestamp(
                timestamp_ns
            )
        )

    @property
    def event_type(self):
        return self._event_type

    @property
    def entity_type(self):
        return self._entity_type

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def sequence(self):
        return self._sequence

    @property
    def timestamp_ns(self):
        return self._timestamp_ns

    @property
    def message_type(self):
        return self._message_type

    @property
    def record(self):
        return copy.deepcopy(
            self._record
        )

    @property
    def changed_fields(self):
        return copy.deepcopy(
            self._changed_fields
        )

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "sequence": self.sequence,
            "timestamp_ns": self.timestamp_ns,
            "message_type": self.message_type,
            "record": self.record,
            "changed_fields": (
                self.changed_fields
            ),
        }

    def __eq__(self, other):
        if not isinstance(
            other,
            StateEvent,
        ):
            return False

        return self.to_dict() == other.to_dict()

    def __repr__(self):
        return (
            "StateEvent("
            "event_type=%r, "
            "entity_type=%r, "
            "entity_id=%r, "
            "sequence=%r, "
            "message_type=%r"
            ")"
            % (
                self.event_type,
                self.entity_type,
                self.entity_id,
                self.sequence,
                self.message_type,
            )
        )

    @staticmethod
    def _validate_event_type(
        event_type,
    ):
        if event_type not in VALID_EVENT_TYPES:
            raise ValueError(
                "invalid event type: %r"
                % event_type
            )

        return event_type

    @staticmethod
    def _validate_text(
        value,
        description,
    ):
        if not isinstance(value, str):
            raise TypeError(
                "%s must be a string"
                % description
            )

        value = value.strip()

        if not value:
            raise ValueError(
                "%s cannot be empty"
                % description
            )

        return value

    @classmethod
    def _validate_optional_text(
        cls,
        value,
        description,
    ):
        if value is None:
            return None

        return cls._validate_text(
            value,
            description,
        )

    @staticmethod
    def _validate_entity_id(
        entity_id,
    ):
        if isinstance(entity_id, bool):
            raise TypeError(
                "entity ID cannot be boolean"
            )

        if isinstance(entity_id, int):
            if entity_id < 0:
                raise ValueError(
                    "entity ID cannot be negative"
                )

            return entity_id

        if isinstance(entity_id, str):
            entity_id = entity_id.strip()

            if not entity_id:
                raise ValueError(
                    "entity ID cannot be empty"
                )

            return entity_id

        raise TypeError(
            "entity ID must be an integer "
            "or string"
        )

    @staticmethod
    def _validate_sequence(
        sequence,
    ):
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
        ):
            raise TypeError(
                "sequence must be an integer"
            )

        if sequence < 0:
            raise ValueError(
                "sequence cannot be negative"
            )

        return sequence

    @staticmethod
    def _validate_timestamp(
        timestamp_ns,
    ):
        if (
            not isinstance(timestamp_ns, int)
            or isinstance(
                timestamp_ns,
                bool,
            )
        ):
            raise TypeError(
                "timestamp must be an integer"
            )

        if timestamp_ns < 0:
            raise ValueError(
                "timestamp cannot be negative"
            )

        return timestamp_ns

    @staticmethod
    def _validate_record(
        record,
    ):
        if record is None:
            return None

        if not isinstance(record, dict):
            raise TypeError(
                "record must be a dictionary"
            )

        return copy.deepcopy(
            record
        )

    @staticmethod
    def _validate_changed_fields(
        changed_fields,
    ):
        if changed_fields is None:
            return {}

        if not isinstance(
            changed_fields,
            dict,
        ):
            raise TypeError(
                "changed fields must be "
                "a dictionary"
            )

        validated = {}

        for field_name, change in (
            changed_fields.items()
        ):
            if not isinstance(
                field_name,
                str,
            ):
                raise TypeError(
                    "changed field name must "
                    "be a string"
                )

            if not isinstance(change, dict):
                raise TypeError(
                    "change for %s must be "
                    "a dictionary"
                    % field_name
                )

            if (
                "old" not in change
                or "new" not in change
            ):
                raise ValueError(
                    "change for %s must contain "
                    "old and new values"
                    % field_name
                )

            validated[field_name] = {
                "old": copy.deepcopy(
                    change["old"]
                ),
                "new": copy.deepcopy(
                    change["new"]
                ),
            }

        return validated
