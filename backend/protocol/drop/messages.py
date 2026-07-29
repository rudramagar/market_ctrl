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
class MarketTradingStateMessage(DropMessage):
    market_index: int
    market_id: int
    state: str
