from dataclasses import dataclass
from threading import RLock
from typing import Optional

from backend.protocol.drop.messages import EntryPointMessage, EntryPointStatusMessage


PROTOCOL_CODES = ("A", "D", "O", "I", "F", "C", "M", "G")


@dataclass(frozen=True)
class EntryPointRecord:
    """Current reconstructed state of one entry point."""

    entry_point_index: int
    host_user_id: int
    client_user_id: int
    protocol: str
    host_address: Optional[int]
    host_port: Optional[int]
    logon_status: Optional[int]
    client_ip_address: Optional[int]
    client_port: Optional[int]
    last_logon_time_ns: Optional[int]
    last_logoff_time_ns: Optional[int]
    logon_count: Optional[int]
    user_event_type: Optional[int]
    definition_sequence: int
    definition_timestamp_ns: int
    status_sequence: int
    status_timestamp_ns: int

    @property
    def key(self):
        return self.entry_point_index, self.host_user_id, self.client_user_id, self.protocol

    @property
    def last_sequence(self):
        return max(self.definition_sequence, self.status_sequence)

    @property
    def last_timestamp_ns(self):
        if self.status_sequence >= self.definition_sequence:
            return self.status_timestamp_ns
        return self.definition_timestamp_ns

    def to_dict(self):
        return {
            "entry_point_index": self.entry_point_index,
            "host_user_id": self.host_user_id,
            "client_user_id": self.client_user_id,
            "protocol": self.protocol,
            "host_address": self.host_address,
            "host_port": self.host_port,
            "logon_status": self.logon_status,
            "client_ip_address": self.client_ip_address,
            "client_port": self.client_port,
            "last_logon_time_ns": self.last_logon_time_ns,
            "last_logoff_time_ns": self.last_logoff_time_ns,
            "logon_count": self.logon_count,
            "user_event_type": self.user_event_type,
            "definition_sequence": self.definition_sequence,
            "definition_timestamp_ns": self.definition_timestamp_ns,
            "status_sequence": self.status_sequence,
            "status_timestamp_ns": self.status_timestamp_ns,
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": self.last_timestamp_ns,
        }


class EntryPointStateStore:
    """Thread-safe in-memory entry-point state store."""

    def __init__(self):
        self._entry_points = {}
        self._lock = RLock()

    @property
    def count(self):
        with self._lock:
            return len(self._entry_points)

    def apply(self, message):
        if isinstance(message, EntryPointMessage):
            return self._apply_entry_point(message)
        if isinstance(message, EntryPointStatusMessage):
            return self._apply_entry_point_status(message)
        return False

    def get_entry_point(self, entry_point_index, host_user_id, client_user_id, protocol):
        key = int(entry_point_index), int(host_user_id), int(client_user_id), str(protocol)
        with self._lock:
            return self._entry_points.get(key)

    def get_entry_points(self):
        with self._lock:
            return tuple(sorted(self._entry_points.values(), key=lambda record: record.key))

    def get_for_user(self, client_user_id):
        client_user_id = int(client_user_id)
        with self._lock:
            records = [record for record in self._entry_points.values() if record.client_user_id == client_user_id]
        return tuple(sorted(records, key=lambda record: record.key))

    def get_preferred_for_user(self, client_user_id):
        records = self.get_for_user(client_user_id)
        if not records:
            return None
        return max(records, key=self._preference_key)

    def snapshot(self):
        return [record.to_dict() for record in self.get_entry_points()]

    def restore(self, records):
        if not isinstance(records, list):
            raise ValueError("entry-point snapshot must be a list")

        restored = {}
        for position, values in enumerate(records):
            if not isinstance(values, dict):
                raise ValueError("entry-point snapshot record %d must be an object" % position)
            record = self._restore_record(values, position)
            if record.key in restored:
                raise ValueError("duplicate entry-point key in snapshot: %r" % (record.key,))
            restored[record.key] = record

        with self._lock:
            self._entry_points = restored
        return len(restored)

    def clear(self):
        with self._lock:
            self._entry_points.clear()

    @classmethod
    def _restore_record(cls, values, position):
        protocol = cls._required_string(values, "protocol", position)
        if protocol not in PROTOCOL_CODES:
            raise ValueError("entry-point snapshot record %d has invalid protocol: %r" % (position, protocol))

        logon_status = cls._optional_int(values, "logon_status", position)
        if logon_status not in (None, 0, 1):
            raise ValueError("entry-point snapshot record %d has invalid logon_status: %r" % (position, logon_status))

        user_event_type = cls._optional_int(values, "user_event_type", position)
        if user_event_type not in (None, 0, 1, 2):
            raise ValueError("entry-point snapshot record %d has invalid user_event_type: %r" % (position, user_event_type))

        definition_sequence = cls._required_int(values, "definition_sequence", position)
        definition_timestamp_ns = cls._required_int(values, "definition_timestamp_ns", position)
        status_sequence = cls._required_int(values, "status_sequence", position)
        status_timestamp_ns = cls._required_int(values, "status_timestamp_ns", position)

        if min(definition_sequence, definition_timestamp_ns, status_sequence, status_timestamp_ns) < 0:
            raise ValueError("entry-point snapshot record %d has a negative sequence or timestamp" % position)

        return EntryPointRecord(
            entry_point_index=cls._required_int(values, "entry_point_index", position),
            host_user_id=cls._required_int(values, "host_user_id", position),
            client_user_id=cls._required_int(values, "client_user_id", position),
            protocol=protocol,
            host_address=cls._optional_int(values, "host_address", position),
            host_port=cls._optional_int(values, "host_port", position),
            logon_status=logon_status,
            client_ip_address=cls._optional_int(values, "client_ip_address", position),
            client_port=cls._optional_int(values, "client_port", position),
            last_logon_time_ns=cls._optional_int(values, "last_logon_time_ns", position),
            last_logoff_time_ns=cls._optional_int(values, "last_logoff_time_ns", position),
            logon_count=cls._optional_int(values, "logon_count", position),
            user_event_type=user_event_type,
            definition_sequence=definition_sequence,
            definition_timestamp_ns=definition_timestamp_ns,
            status_sequence=status_sequence,
            status_timestamp_ns=status_timestamp_ns,
        )

    @staticmethod
    def _required_int(values, name, position):
        if name not in values:
            raise ValueError("entry-point snapshot record %d is missing %s" % (position, name))
        value = values[name]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("entry-point snapshot record %d field %s must be an integer" % (position, name))
        return value

    @staticmethod
    def _optional_int(values, name, position):
        value = values.get(name)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("entry-point snapshot record %d field %s must be an integer or null" % (position, name))
        return value

    @staticmethod
    def _required_string(values, name, position):
        if name not in values:
            raise ValueError("entry-point snapshot record %d is missing %s" % (position, name))
        value = values[name]
        if not isinstance(value, str):
            raise ValueError("entry-point snapshot record %d field %s must be a string" % (position, name))
        return value

    def _apply_entry_point(self, message):
        sequence = message.mercury_header.matching_engine_sequence
        timestamp_ns = message.mercury_header.timestamp_nanoseconds
        key = self._message_key(message)

        with self._lock:
            current = self._entry_points.get(key)
            if current is not None and sequence <= current.definition_sequence:
                return False

            status_values = self._empty_status_values()
            if current is not None:
                status_values = self._status_values(current)

            self._entry_points[key] = EntryPointRecord(
                entry_point_index=message.entry_point_index,
                host_user_id=message.host_user_id,
                client_user_id=message.client_user_id,
                protocol=message.protocol,
                host_address=message.host_address,
                host_port=message.host_port,
                definition_sequence=sequence,
                definition_timestamp_ns=timestamp_ns,
                **status_values
            )
            return True

    def _apply_entry_point_status(self, message):
        sequence = message.mercury_header.matching_engine_sequence
        timestamp_ns = message.mercury_header.timestamp_nanoseconds
        key = self._message_key(message)

        with self._lock:
            current = self._entry_points.get(key)
            if current is not None and sequence <= max(current.definition_sequence, current.status_sequence):
                return False

            self._entry_points[key] = EntryPointRecord(
                entry_point_index=message.entry_point_index,
                host_user_id=message.host_user_id,
                client_user_id=message.client_user_id,
                protocol=message.protocol,
                host_address=current.host_address if current is not None else None,
                host_port=current.host_port if current is not None else None,
                logon_status=message.logon_status,
                client_ip_address=message.client_ip_address,
                client_port=message.client_port,
                last_logon_time_ns=message.last_logon_time_ns,
                last_logoff_time_ns=message.last_logoff_time_ns,
                logon_count=message.logon_count,
                user_event_type=message.user_event_type,
                definition_sequence=current.definition_sequence if current is not None else 0,
                definition_timestamp_ns=current.definition_timestamp_ns if current is not None else 0,
                status_sequence=sequence,
                status_timestamp_ns=timestamp_ns,
            )
            return True

    @staticmethod
    def _message_key(message):
        return message.entry_point_index, message.host_user_id, message.client_user_id, message.protocol

    @staticmethod
    def _empty_status_values():
        return {
            "logon_status": None,
            "client_ip_address": None,
            "client_port": None,
            "last_logon_time_ns": None,
            "last_logoff_time_ns": None,
            "logon_count": None,
            "user_event_type": None,
            "status_sequence": 0,
            "status_timestamp_ns": 0,
        }

    @staticmethod
    def _status_values(record):
        return {
            "logon_status": record.logon_status,
            "client_ip_address": record.client_ip_address,
            "client_port": record.client_port,
            "last_logon_time_ns": record.last_logon_time_ns,
            "last_logoff_time_ns": record.last_logoff_time_ns,
            "logon_count": record.logon_count,
            "user_event_type": record.user_event_type,
            "status_sequence": record.status_sequence,
            "status_timestamp_ns": record.status_timestamp_ns,
        }

    @staticmethod
    def _preference_key(record):
        return (
            1 if record.logon_status == 0 else 0,
            1 if record.logon_status is not None else 0,
            record.status_sequence,
            record.last_timestamp_ns,
            record.entry_point_index,
        )

