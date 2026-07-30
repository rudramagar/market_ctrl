from dataclasses import (
    dataclass,
    fields,
)
from threading import RLock

from backend.protocol.drop.messages import (
    SystemEventMessage,
    TradeDateMessage,
    TradingEngineStateMessage,
)


SYSTEM_EVENT_NAMES = {
    0: "INIT",
    1: "START_MESSAGES",
    2: "END_MESSAGES",
    3: "PREV_DAY",
    4: "NEXT_DAY",
    5: "START_DAY",
    6: "END_DAY",
    7: "SPIN",
    8: "OPEN",
    9: "CLOSE",
    10: "START_MATCHING",
    11: "END_MATCHING",
    12: "CROSS",
    13: "PREOPEN_MARGIN_TRADING",
    14: "OPEN_MARGIN_TRADING",
    15: "BREAK_MARGIN_TRADING",
    16: "CLOSE_MARGIN_TRADING",
    17: "END_SESSION",
}

SYSTEM_EVENT_STATE_NAMES = {
    0: "PENDING",
    1: "DISPATCHED",
    2: "FAILED",
}


@dataclass(frozen=True)
class TradingEngineStateRecord:
    """Latest trading-engine session metadata."""

    trade_date: int
    calendar_date: int
    session_start_date: int
    session_id: str
    version_id: str
    trading_session_mode: str
    time_zone: str
    exec_id_base: str
    fix_security_id_source: str
    ouch_security_id_source: str
    tiers_number: int
    enable_fix_inbound_order_replication: bool
    enable_ouch_order_replication: bool
    enable_fix_burst_cancel: bool
    fix_comp_id: str
    matching_engine_version: str
    matching_engine_node_count: int
    gateway_count: int
    max_record: int
    order_store_capacity: int
    order_store_warning_threshold: int
    trade_store_capacity: int
    trade_store_warning_threshold: int
    price_limits_capacity: int
    price_limits_warning_threshold: int
    aeron_archive_capacity: int
    aeron_archive_warning_threshold: int
    monitoring_enabled: bool
    monitoring_aeron_stat: bool
    monitoring_allocator_stat: bool
    monitoring_interval_ms: int
    performance_statistics_enabled: bool
    performance_warmup_messages: int
    performance_print_interval_messages: int
    performance_print_interval_time: int
    performance_value_scale: int
    performance_in_flight: bool
    sequence: int
    timestamp_ns: int

    @property
    def last_sequence(self):
        return self.sequence

    @property
    def last_timestamp_ns(self):
        return self.timestamp_ns

    def to_dict(self):
        return {
            "trade_date": self.trade_date,
            "calendar_date": self.calendar_date,
            "session_start_date": (
                self.session_start_date
            ),
            "session_id": self.session_id,
            "version_id": self.version_id,
            "trading_session_mode": (
                self.trading_session_mode
            ),
            "time_zone": self.time_zone,
            "exec_id_base": self.exec_id_base,
            "fix_security_id_source": (
                self.fix_security_id_source
            ),
            "ouch_security_id_source": (
                self.ouch_security_id_source
            ),
            "tiers_number": self.tiers_number,
            "enable_fix_inbound_order_replication": (
                self
                .enable_fix_inbound_order_replication
            ),
            "enable_ouch_order_replication": (
                self.enable_ouch_order_replication
            ),
            "enable_fix_burst_cancel": (
                self.enable_fix_burst_cancel
            ),
            "fix_comp_id": self.fix_comp_id,
            "matching_engine_version": (
                self.matching_engine_version
            ),
            "matching_engine_node_count": (
                self.matching_engine_node_count
            ),
            "gateway_count": self.gateway_count,
            "max_record": self.max_record,
            "order_store_capacity": (
                self.order_store_capacity
            ),
            "order_store_warning_threshold": (
                self.order_store_warning_threshold
            ),
            "trade_store_capacity": (
                self.trade_store_capacity
            ),
            "trade_store_warning_threshold": (
                self.trade_store_warning_threshold
            ),
            "price_limits_capacity": (
                self.price_limits_capacity
            ),
            "price_limits_warning_threshold": (
                self.price_limits_warning_threshold
            ),
            "aeron_archive_capacity": (
                self.aeron_archive_capacity
            ),
            "aeron_archive_warning_threshold": (
                self.aeron_archive_warning_threshold
            ),
            "monitoring_enabled": (
                self.monitoring_enabled
            ),
            "monitoring_aeron_stat": (
                self.monitoring_aeron_stat
            ),
            "monitoring_allocator_stat": (
                self.monitoring_allocator_stat
            ),
            "monitoring_interval_ms": (
                self.monitoring_interval_ms
            ),
            "performance_statistics_enabled": (
                self.performance_statistics_enabled
            ),
            "performance_warmup_messages": (
                self.performance_warmup_messages
            ),
            "performance_print_interval_messages": (
                self
                .performance_print_interval_messages
            ),
            "performance_print_interval_time": (
                self.performance_print_interval_time
            ),
            "performance_value_scale": (
                self.performance_value_scale
            ),
            "performance_in_flight": (
                self.performance_in_flight
            ),
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": (
                self.last_timestamp_ns
            ),
        }


@dataclass(frozen=True)
class TradeDateRecord:
    """Latest authoritative trade and calendar dates."""

    trade_date: int
    calendar_date: int
    sequence: int
    timestamp_ns: int

    @property
    def last_sequence(self):
        return self.sequence

    @property
    def last_timestamp_ns(self):
        return self.timestamp_ns

    def to_dict(self):
        return {
            "trade_date": self.trade_date,
            "calendar_date": self.calendar_date,
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": (
                self.last_timestamp_ns
            ),
        }


@dataclass(frozen=True)
class SystemEventRecord:
    """Latest state for one system-event type."""

    engine_time_ns: int
    priority: int
    system_event_index: int
    system_event_type: int
    orderbook_index: int
    market_id: int
    security_id: int
    event_state: int
    event_time_ns: int
    actual_event_time_ns: int
    sequence: int
    timestamp_ns: int

    @property
    def event_name(self):
        return SYSTEM_EVENT_NAMES.get(
            self.system_event_type,
            "UNKNOWN",
        )

    @property
    def event_state_name(self):
        return SYSTEM_EVENT_STATE_NAMES.get(
            self.event_state,
            "UNKNOWN",
        )

    @property
    def last_sequence(self):
        return self.sequence

    @property
    def last_timestamp_ns(self):
        return self.timestamp_ns

    def to_dict(self):
        return {
            "engine_time_ns": self.engine_time_ns,
            "priority": self.priority,
            "system_event_index": (
                self.system_event_index
            ),
            "system_event_type": (
                self.system_event_type
            ),
            "event_name": self.event_name,
            "orderbook_index": (
                self.orderbook_index
            ),
            "market_id": self.market_id,
            "security_id": self.security_id,
            "event_state": self.event_state,
            "event_state_name": (
                self.event_state_name
            ),
            "event_time_ns": self.event_time_ns,
            "actual_event_time_ns": (
                self.actual_event_time_ns
            ),
            "last_sequence": self.last_sequence,
            "last_timestamp_ns": (
                self.last_timestamp_ns
            ),
        }


class SessionStateStore:
    """Thread-safe current-session metadata store."""

    def __init__(self):
        self._trading_engine = None
        self._trade_date = None
        self._system_events = {}
        self._last_system_event = None
        self._lock = RLock()

    @property
    def trading_engine(self):
        with self._lock:
            return self._trading_engine

    @property
    def trade_date_record(self):
        with self._lock:
            return self._trade_date

    @property
    def last_system_event(self):
        with self._lock:
            return self._last_system_event

    @property
    def event_count(self):
        with self._lock:
            return len(self._system_events)

    @property
    def trade_date(self):
        with self._lock:
            if self._trade_date is not None:
                return self._trade_date.trade_date

            if self._trading_engine is not None:
                return self._trading_engine.trade_date

            return None

    @property
    def calendar_date(self):
        with self._lock:
            if self._trade_date is not None:
                return self._trade_date.calendar_date

            if self._trading_engine is not None:
                return self._trading_engine.calendar_date

            return None

    @property
    def session_id(self):
        with self._lock:
            if self._trading_engine is None:
                return None

            return self._trading_engine.session_id

    @property
    def session_start_date(self):
        with self._lock:
            if self._trading_engine is None:
                return None

            return (
                self._trading_engine
                .session_start_date
            )

    @property
    def end_session_dispatched(self):
        with self._lock:
            event = self._system_events.get(17)

            return (
                event is not None
                and event.event_state == 1
            )

    def apply(self, message):
        if isinstance(
            message,
            TradingEngineStateMessage,
        ):
            return self._apply_trading_engine(
                message
            )

        if isinstance(message, TradeDateMessage):
            return self._apply_trade_date(
                message
            )

        if isinstance(message, SystemEventMessage):
            return self._apply_system_event(
                message
            )

        return False

    def get_system_event(
        self,
        system_event_type,
    ):
        system_event_type = int(
            system_event_type
        )

        with self._lock:
            return self._system_events.get(
                system_event_type
            )

    def get_system_events(self):
        with self._lock:
            return tuple(
                sorted(
                    self._system_events.values(),
                    key=lambda event: (
                        event.system_event_type,
                        event.last_sequence,
                    ),
                )
            )

    def snapshot(self):
        with self._lock:
            trading_engine = (
                self._trading_engine
            )
            trade_date = self._trade_date
            system_events = tuple(
                sorted(
                    self._system_events.values(),
                    key=lambda event: (
                        event.system_event_type,
                        event.last_sequence,
                    ),
                )
            )
            last_system_event = (
                self._last_system_event
            )

        return {
            "trading_engine": (
                trading_engine.to_dict()
                if trading_engine is not None
                else None
            ),
            "trade_date": (
                trade_date.to_dict()
                if trade_date is not None
                else None
            ),
            "system_events": [
                event.to_dict()
                for event in system_events
            ],
            "last_system_event": (
                last_system_event.to_dict()
                if last_system_event is not None
                else None
            ),
            "end_session_dispatched": (
                self.end_session_dispatched
            ),
        }

    def restore(self, snapshot):
        """
        Replace current-session metadata from a snapshot.

        All records are validated before the current
        session state is changed.
        """

        if not isinstance(snapshot, dict):
            raise ValueError(
                "session snapshot must be an object"
            )

        system_event_values = snapshot.get(
            "system_events"
        )

        if not isinstance(
            system_event_values,
            list,
        ):
            raise ValueError(
                "system_events snapshot must be a list"
            )

        trading_engine = None
        trading_engine_values = snapshot.get(
            "trading_engine"
        )

        if trading_engine_values is not None:
            trading_engine = (
                self._restore_record(
                    TradingEngineStateRecord,
                    trading_engine_values,
                    "trading engine",
                )
            )

        trade_date = None
        trade_date_values = snapshot.get(
            "trade_date"
        )

        if trade_date_values is not None:
            trade_date = self._restore_record(
                TradeDateRecord,
                trade_date_values,
                "trade date",
            )

        system_events = {}

        for position, values in enumerate(
            system_event_values
        ):
            record = self._restore_record(
                SystemEventRecord,
                values,
                "system event %d"
                % position,
            )

            if record.event_state not in (
                0,
                1,
                2,
            ):
                raise ValueError(
                    "system event %d has invalid "
                    "event_state: %d"
                    % (
                        position,
                        record.event_state,
                    )
                )

            if (
                record.system_event_type
                in system_events
            ):
                raise ValueError(
                    "duplicate system event type: %d"
                    % record.system_event_type
                )

            system_events[
                record.system_event_type
            ] = record

        last_system_event = None
        last_event_values = snapshot.get(
            "last_system_event"
        )

        if last_event_values is not None:
            last_system_event = (
                self._restore_record(
                    SystemEventRecord,
                    last_event_values,
                    "last system event",
                )
            )

            stored_event = system_events.get(
                last_system_event
                .system_event_type
            )

            if stored_event != last_system_event:
                raise ValueError(
                    "last_system_event does not "
                    "match system_events"
                )

        elif system_events:
            last_system_event = max(
                system_events.values(),
                key=lambda record: (
                    record.sequence,
                    record.system_event_type,
                ),
            )

        calculated_end_session = (
            17 in system_events
            and system_events[17].event_state == 1
        )

        saved_end_session = snapshot.get(
            "end_session_dispatched"
        )

        if saved_end_session is not None:
            if not isinstance(
                saved_end_session,
                bool,
            ):
                raise ValueError(
                    "end_session_dispatched must "
                    "be a boolean"
                )

            if (
                saved_end_session
                != calculated_end_session
            ):
                raise ValueError(
                    "end_session_dispatched does not "
                    "match system event 17"
                )

        with self._lock:
            self._trading_engine = trading_engine
            self._trade_date = trade_date
            self._system_events = system_events
            self._last_system_event = (
                last_system_event
            )

        return {
            "trading_engine": (
                1
                if trading_engine is not None
                else 0
            ),
            "trade_date": (
                1
                if trade_date is not None
                else 0
            ),
            "system_events": len(
                system_events
            ),
        }

    def clear(self):
        with self._lock:
            self._trading_engine = None
            self._trade_date = None
            self._system_events.clear()
            self._last_system_event = None

    @staticmethod
    def _restore_record(
        record_type,
        values,
        record_name,
    ):
        if not isinstance(values, dict):
            raise ValueError(
                "%s snapshot must be an object"
                % record_name
            )

        restored_values = {}

        for record_field in fields(
            record_type
        ):
            field_name = record_field.name

            if field_name == "sequence":
                snapshot_name = "last_sequence"

            elif field_name == "timestamp_ns":
                snapshot_name = (
                    "last_timestamp_ns"
                )

            else:
                snapshot_name = field_name

            if snapshot_name not in values:
                raise ValueError(
                    "%s snapshot is missing %s"
                    % (
                        record_name,
                        snapshot_name,
                    )
                )

            value = values[snapshot_name]
            expected_type = record_field.type

            if expected_type is bool:
                valid = isinstance(value, bool)

            elif expected_type is int:
                valid = (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                )

            elif expected_type is str:
                valid = isinstance(value, str)

            else:
                valid = True

            if not valid:
                raise ValueError(
                    "%s snapshot field %s has "
                    "an invalid type"
                    % (
                        record_name,
                        snapshot_name,
                    )
                )

            if (
                field_name in (
                    "sequence",
                    "timestamp_ns",
                )
                and value < 0
            ):
                raise ValueError(
                    "%s snapshot field %s "
                    "cannot be negative"
                    % (
                        record_name,
                        snapshot_name,
                    )
                )

            restored_values[
                field_name
            ] = value

        return record_type(
            **restored_values
        )

    def _apply_trading_engine(
        self,
        message,
    ):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._trading_engine

            if (
                current is not None
                and sequence <= current.sequence
            ):
                return False

            self._trading_engine = (
                TradingEngineStateRecord(
                    trade_date=message.trade_date,
                    calendar_date=(
                        message.calendar_date
                    ),
                    session_start_date=(
                        message.session_start_date
                    ),
                    session_id=message.session_id,
                    version_id=message.version_id,
                    trading_session_mode=(
                        message.trading_session_mode
                    ),
                    time_zone=message.time_zone,
                    exec_id_base=(
                        message.exec_id_base
                    ),
                    fix_security_id_source=(
                        message.fix_security_id_source
                    ),
                    ouch_security_id_source=(
                        message.ouch_security_id_source
                    ),
                    tiers_number=(
                        message.tiers_number
                    ),
                    enable_fix_inbound_order_replication=(
                        message
                        .enable_fix_inbound_order_replication
                    ),
                    enable_ouch_order_replication=(
                        message
                        .enable_ouch_order_replication
                    ),
                    enable_fix_burst_cancel=(
                        message
                        .enable_fix_burst_cancel
                    ),
                    fix_comp_id=(
                        message.fix_comp_id
                    ),
                    matching_engine_version=(
                        message
                        .matching_engine_version
                    ),
                    matching_engine_node_count=(
                        message
                        .matching_engine_node_count
                    ),
                    gateway_count=(
                        message.gateway_count
                    ),
                    max_record=message.max_record,
                    order_store_capacity=(
                        message
                        .order_store_capacity
                    ),
                    order_store_warning_threshold=(
                        message
                        .order_store_warning_threshold
                    ),
                    trade_store_capacity=(
                        message
                        .trade_store_capacity
                    ),
                    trade_store_warning_threshold=(
                        message
                        .trade_store_warning_threshold
                    ),
                    price_limits_capacity=(
                        message
                        .price_limits_capacity
                    ),
                    price_limits_warning_threshold=(
                        message
                        .price_limits_warning_threshold
                    ),
                    aeron_archive_capacity=(
                        message
                        .aeron_archive_capacity
                    ),
                    aeron_archive_warning_threshold=(
                        message
                        .aeron_archive_warning_threshold
                    ),
                    monitoring_enabled=(
                        message.monitoring_enabled
                    ),
                    monitoring_aeron_stat=(
                        message.monitoring_aeron_stat
                    ),
                    monitoring_allocator_stat=(
                        message
                        .monitoring_allocator_stat
                    ),
                    monitoring_interval_ms=(
                        message.monitoring_interval_ms
                    ),
                    performance_statistics_enabled=(
                        message
                        .performance_statistics_enabled
                    ),
                    performance_warmup_messages=(
                        message
                        .performance_warmup_messages
                    ),
                    performance_print_interval_messages=(
                        message
                        .performance_print_interval_messages
                    ),
                    performance_print_interval_time=(
                        message
                        .performance_print_interval_time
                    ),
                    performance_value_scale=(
                        message.performance_value_scale
                    ),
                    performance_in_flight=(
                        message.performance_in_flight
                    ),
                    sequence=sequence,
                    timestamp_ns=timestamp_ns,
                )
            )

            return True

    def _apply_trade_date(
        self,
        message,
    ):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._trade_date

            if (
                current is not None
                and sequence <= current.sequence
            ):
                return False

            self._trade_date = TradeDateRecord(
                trade_date=message.trade_date,
                calendar_date=(
                    message.calendar_date
                ),
                sequence=sequence,
                timestamp_ns=timestamp_ns,
            )

            return True

    def _apply_system_event(
        self,
        message,
    ):
        sequence = (
            message.mercury_header
            .matching_engine_sequence
        )
        timestamp_ns = (
            message.mercury_header
            .timestamp_nanoseconds
        )

        with self._lock:
            current = self._system_events.get(
                message.system_event_type
            )

            if (
                current is not None
                and sequence <= current.sequence
            ):
                return False

            record = SystemEventRecord(
                engine_time_ns=(
                    message.engine_time_ns
                ),
                priority=message.priority,
                system_event_index=(
                    message.system_event_index
                ),
                system_event_type=(
                    message.system_event_type
                ),
                orderbook_index=(
                    message.orderbook_index
                ),
                market_id=message.market_id,
                security_id=message.security_id,
                event_state=message.event_state,
                event_time_ns=(
                    message.event_time_ns
                ),
                actual_event_time_ns=(
                    message.actual_event_time_ns
                ),
                sequence=sequence,
                timestamp_ns=timestamp_ns,
            )

            self._system_events[
                message.system_event_type
            ] = record

            if (
                self._last_system_event is None
                or sequence
                > self._last_system_event.sequence
            ):
                self._last_system_event = record

            return True
