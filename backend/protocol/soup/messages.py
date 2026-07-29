from dataclasses import dataclass

@dataclass(frozen=True)
class SoupPacket:
    packet_type: str
    payload: bytes = b""

@dataclass(frozen=True)
class SoupLoginAccepted:
    session: str
    sequence: int
