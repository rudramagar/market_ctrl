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

class ApiError(ProtocolError):
    """API message error."""

class ApiRequestRejectedError(ApiError):
    """Matching engine rejected an API request."""

    def __init__(
        self,
        correlation_id,
        reject_reason,
        reject_text,
    ):
        self.correlation_id = correlation_id
        self.reject_reason = reject_reason
        self.reject_text = reject_text

        super().__init__(
            "API request rejected: code=%d reason=%s"
            % (reject_reason, reject_text)
        )

class DropFormatError(ProtocolError):
    """DROP message format error."""

class ControlError(Exception):
    """Base control workflow error."""

class ControlTimeoutError(ControlError):
    """DROP did not confirm a control request in time."""
