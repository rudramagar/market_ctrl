from dataclasses import dataclass


@dataclass(frozen=True)
class SbeHeader:
    block_length: int
    template_id: int
    schema_id: int
    version: int


@dataclass(frozen=True)
class MercuryHeader:
    timestamp_nanoseconds: int
    matching_engine_sequence: int


@dataclass(frozen=True)
class DropMessage:
    sbe_header: SbeHeader
    mercury_header: MercuryHeader


@dataclass(frozen=True)
class UserMessage(DropMessage):
    user_index: int
    user_id: int
    user_name: str
    liquidity_provider: bool
    state: str
    firm_index: int
    firm_id: int
    executing_firm: str
    capacity: str
    clearing_firm: str
    clearing_ref: str
    allow_override: bool
    live_order_limit: int
    user_type_id: int


@dataclass(frozen=True)
class UserTypeMessage(DropMessage):
    user_type_index: int
    user_type_id: int
    user_type_name: str


@dataclass(frozen=True)
class MarketMessage(DropMessage):
    market_index: int
    market_id: int
    market_name: str
    market_trading_session: int


@dataclass(frozen=True)
class FirmMessage(DropMessage):
    firm_index: int
    firm_id: int
    firm_code: str
    psms_code: str
    firm_name: str
    firm_type: str
    state: str


@dataclass(frozen=True)
class SystemEventMessage(DropMessage):
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


@dataclass(frozen=True)
class EntryPointMessage(DropMessage):
    entry_point_index: int
    host_user_id: int
    client_user_id: int
    protocol: str
    host_address: int
    host_port: int


@dataclass(frozen=True)
class EntryPointStatusMessage(DropMessage):
    entry_point_index: int
    host_user_id: int
    client_user_id: int
    protocol: str
    logon_status: int
    client_ip_address: int
    client_port: int
    last_logon_time_ns: int
    last_logoff_time_ns: int
    logon_count: int
    user_event_type: int


@dataclass(frozen=True)
class FirmStatusMessage(DropMessage):
    firm_index: int
    firm_id: int
    state: str


@dataclass(frozen=True)
class UserStatusMessage(DropMessage):
    user_index: int
    user_id: int
    state: str


@dataclass(frozen=True)
class TradingEngineStateMessage(DropMessage):
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


@dataclass(frozen=True)
class MarketTradingPhaseMessage(DropMessage):
    market_index: int
    market_id: int
    phase: int


@dataclass(frozen=True)
class MarketTradingStateMessage(DropMessage):
    market_index: int
    market_id: int
    state: str


@dataclass(frozen=True)
class UserMarketMessage(DropMessage):
    user_market_index: int
    user_id: int
    market_id: int


@dataclass(frozen=True)
class TradeDateMessage(DropMessage):
    trade_date: int
    calendar_date: int
