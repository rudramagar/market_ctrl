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

    def __init__(
        self,
        reason,
        message=None,
    ):
        self.reason = reason

        if message is None:
            message = (
                "Soup login rejected: %s"
                % reason
            )

        super().__init__(message)


class SoupEndOfSessionError(SoupError):
    """SoupBinTCP session ended."""


class DropResumeError(ProtocolError):
    """DROP could not resume at the requested checkpoint."""

    def __init__(
        self,
        requested_session,
        accepted_session,
        requested_sequence,
        accepted_sequence,
    ):
        self.requested_session = (
            requested_session
        )
        self.accepted_session = (
            accepted_session
        )
        self.requested_sequence = int(
            requested_sequence
        )
        self.accepted_sequence = int(
            accepted_sequence
        )

        super().__init__(
            "DROP resume mismatch: "
            "requested_session=%r "
            "accepted_session=%r "
            "requested_sequence=%d "
            "accepted_sequence=%d"
            % (
                requested_session,
                accepted_session,
                self.requested_sequence,
                self.accepted_sequence,
            )
        )


class ApiError(ProtocolError):
    """API message error."""


class ApiConnectionLostError(ApiError):
    """
    API connection was lost while processing a request.

    The request may already have reached the matching engine,
    so callers must not blindly resend it.
    """

    def __init__(
        self,
        correlation_id,
        request_may_have_been_sent,
        cause,
    ):
        self.correlation_id = correlation_id
        self.request_may_have_been_sent = bool(
            request_may_have_been_sent
        )
        self.cause = cause

        super().__init__(
            "API connection lost: "
            "correlation_id=%d "
            "request_may_have_been_sent=%s "
            "cause=%s"
            % (
                correlation_id,
                self.request_may_have_been_sent,
                cause,
            )
        )


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
            "API request rejected: "
            "code=%d reason=%s"
            % (
                reject_reason,
                reject_text,
            )
        )


class DropFormatError(ProtocolError):
    """DROP message format error."""


class ControlError(Exception):
    """Base control workflow error."""


class ControlTimeoutError(ControlError):
    """DROP did not confirm a control request in time."""
