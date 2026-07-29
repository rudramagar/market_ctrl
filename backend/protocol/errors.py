class ProtocolError(Exception):
    """Base protocol error."""


class TransportError(ProtocolError):
    """TCP transport error."""


class ConnectionClosedError(TransportError):
    """Remote peer closed the connection."""


class SoupError(ProtocolError):
    """SoupBinTCP protocol error."""


class SoupLoginRejectedError(SoupError):
    """SoupBinTCP login was rejected."""


class SoupEndOfSessionError(SoupError):
    """SoupBinTCP session ended."""
