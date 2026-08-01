import logging
import time

from backend.protocol.drop.message_format import (
    DropMessageDecoder,
)
from backend.protocol.errors import (
    ConnectionClosedError,
    DropFormatError,
    DropResumeError,
    ProtocolError,
    SoupEndOfSessionError,
)
from backend.protocol.soup.session import SoupSession
from backend.protocol.transport.socket import TcpSocket


logger = logging.getLogger(__name__)


class DropClient:
    """Receive and decode DROP messages over SoupBinTCP."""

    def __init__(
        self,
        host,
        port,
        username,
        password,
        timeout_seconds=10.0,
        liveness_timeout_seconds=None,
        decoder=None,
        strict_templates=False,
    ):
        if not host:
            raise ValueError(
                "DROP host is required"
            )

        if not username:
            raise ValueError(
                "DROP username is required"
            )

        if password is None:
            raise ValueError(
                "DROP password is required"
            )

        port = int(port)

        if port < 1 or port > 65535:
            raise ValueError(
                "invalid DROP port: %d"
                % port
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout_seconds = float(
            timeout_seconds
        )

        if self.timeout_seconds <= 0:
            raise ValueError(
                "DROP timeout must be greater than zero"
            )

        if liveness_timeout_seconds is None:
            liveness_timeout_seconds = (
                self.timeout_seconds
            )

        self.liveness_timeout_seconds = float(
            liveness_timeout_seconds
        )

        if self.liveness_timeout_seconds <= 0:
            raise ValueError(
                "DROP liveness timeout must be "
                "greater than zero"
            )

        self.strict_templates = bool(
            strict_templates
        )

        self.decoder = (
            decoder
            if decoder is not None
            else DropMessageDecoder()
        )

        self._tcp_socket = None
        self._soup_session = None
        self._connected = False

        self._requested_session = None
        self._accepted_session = None

        self._requested_sequence_number = None
        self._accepted_sequence_number = None
        self._next_sequence_number = None

        self._last_disconnect_reason = None
        self._unsupported_template_ids = set()

        self._last_packet_received_monotonic = None

    @property
    def connected(self):
        return self._connected

    @property
    def live(self):
        if not self._connected:
            return False

        age = self.last_packet_age_seconds

        if age is None:
            return False

        return (
            age <= self.liveness_timeout_seconds
        )

    @property
    def last_packet_age_seconds(self):
        received_at = (
            self._last_packet_received_monotonic
        )

        if received_at is None:
            return None

        age = time.monotonic() - received_at

        if age < 0:
            return 0.0

        return age

    @property
    def requested_session(self):
        return self._requested_session

    @property
    def accepted_session(self):
        return self._accepted_session

    @property
    def requested_sequence_number(self):
        return self._requested_sequence_number

    @property
    def accepted_sequence_number(self):
        return self._accepted_sequence_number

    @property
    def next_sequence_number(self):
        return self._next_sequence_number

    @property
    def last_disconnect_reason(self):
        return self._last_disconnect_reason

    @property
    def unsupported_template_ids(self):
        return set(
            self._unsupported_template_ids
        )

    def connect(
        self,
        session="",
        sequence_number=1,
    ):
        """Connect and log in to the requested DROP checkpoint."""

        if self._connected:
            return

        sequence_number = int(
            sequence_number
        )

        if sequence_number < 1:
            raise ValueError(
                "sequence number must be at least 1"
            )

        requested_session = (
            session
            if session is not None
            else ""
        )

        tcp_socket = TcpSocket(
            self.host,
            self.port,
            timeout_seconds=self.timeout_seconds,
        )
        soup_session = SoupSession(
            tcp_socket
        )

        try:
            soup_session.connect()

            accepted = soup_session.login(
                username=self.username,
                password=self.password,
                session=requested_session,
                sequence=sequence_number,
            )

            self._validate_login_acceptance(
                requested_session=(
                    requested_session
                ),
                requested_sequence=(
                    sequence_number
                ),
                accepted_session=(
                    accepted.session
                ),
                accepted_sequence=(
                    accepted.sequence
                ),
            )

        except Exception:
            soup_session.close()
            raise

        self._tcp_socket = tcp_socket
        self._soup_session = soup_session
        self._connected = True

        self._requested_session = (
            requested_session
        )
        self._accepted_session = (
            accepted.session
        )

        self._requested_sequence_number = (
            sequence_number
        )
        self._accepted_sequence_number = (
            accepted.sequence
        )

        self._next_sequence_number = (
            soup_session.next_sequence
        )

        self._last_packet_received_monotonic = (
            time.monotonic()
        )
        self._last_disconnect_reason = None

        logger.info(
            "DROP login accepted: "
            "requested_session=%r "
            "accepted_session=%r "
            "sequence=%d",
            requested_session,
            accepted.session,
            accepted.sequence,
        )

    def receive(self):
        """Return the next supported decoded DROP message."""

        if not self._connected:
            raise ProtocolError(
                "DROP client is not connected"
            )

        while self._connected:
            try:
                packet = (
                    self._soup_session
                    .receive_packet()
                )

                self._mark_packet_received()
                self._synchronize_sequence()

            except ConnectionClosedError:
                self._last_disconnect_reason = (
                    "connection_closed"
                )
                self._mark_disconnected()
                return None

            except SoupEndOfSessionError:
                self._last_disconnect_reason = (
                    "end_of_session"
                )
                self._mark_disconnected()
                return None

            except ProtocolError:
                self._last_disconnect_reason = (
                    "connection_error"
                )
                self._mark_disconnected()
                raise

            except OSError:
                self._last_disconnect_reason = (
                    "connection_error"
                )
                self._mark_disconnected()
                raise

            packet_type = (
                self._normalize_packet_type(
                    packet.packet_type
                )
            )

            if packet_type == "H":
                try:
                    self._soup_session.send_heartbeat()

                except (
                    ProtocolError,
                    OSError,
                ):
                    self._last_disconnect_reason = (
                        "connection_error"
                    )
                    self._mark_disconnected()
                    raise

                continue

            if packet_type != "S":
                logger.debug(
                    "ignored Soup packet type: %s",
                    packet_type,
                )
                continue

            template_id = (
                self.decoder.get_template_id(
                    packet.payload
                )
            )

            if not self.decoder.supports(
                packet.payload
            ):
                self._handle_unsupported_template(
                    template_id
                )
                continue

            return self.decoder.decode(
                packet.payload
            )

        return None

    def close(self):
        """Close the DROP Soup session."""

        soup_session = self._soup_session
        was_connected = self._connected

        self._connected = False
        self._soup_session = None
        self._tcp_socket = None

        if was_connected:
            self._last_disconnect_reason = (
                "client_closed"
            )

        if soup_session is None:
            return

        self._capture_sequence(
            soup_session
        )

        try:
            if was_connected:
                soup_session.logout()

        except (
            ConnectionClosedError,
            SoupEndOfSessionError,
            ProtocolError,
            OSError,
        ):
            pass

        finally:
            soup_session.close()

    def _validate_login_acceptance(
        self,
        requested_session,
        requested_sequence,
        accepted_session,
        accepted_sequence,
    ):
        """
        Verify that the server accepted the exact checkpoint.

        A blank requested session allows the server to select
        the current Soup session. An explicit session must match.
        The accepted sequence must always match exactly.
        """

        session_mismatch = (
            bool(requested_session)
            and accepted_session
            != requested_session
        )

        sequence_mismatch = (
            int(accepted_sequence)
            != int(requested_sequence)
        )

        if (
            session_mismatch
            or sequence_mismatch
        ):
            raise DropResumeError(
                requested_session=(
                    requested_session
                ),
                accepted_session=(
                    accepted_session
                ),
                requested_sequence=(
                    requested_sequence
                ),
                accepted_sequence=(
                    accepted_sequence
                ),
            )

    def _synchronize_sequence(self):
        soup_session = self._soup_session

        if soup_session is None:
            return

        self._capture_sequence(
            soup_session
        )

    def _capture_sequence(
        self,
        soup_session,
    ):
        next_sequence = (
            soup_session.next_sequence
        )

        if next_sequence is not None:
            self._next_sequence_number = (
                next_sequence
            )

    def _handle_unsupported_template(
        self,
        template_id,
    ):
        if self.strict_templates:
            raise DropFormatError(
                "unsupported DROP template: %d"
                % template_id
            )

        if (
            template_id
            in self._unsupported_template_ids
        ):
            return

        self._unsupported_template_ids.add(
            template_id
        )

        logger.warning(
            "unsupported DROP template: %d",
            template_id,
        )

    def _mark_packet_received(self):
        self._last_packet_received_monotonic = (
            time.monotonic()
        )

    def _mark_disconnected(self):
        soup_session = self._soup_session

        self._connected = False
        self._soup_session = None
        self._tcp_socket = None

        if soup_session is not None:
            self._capture_sequence(
                soup_session
            )
            soup_session.close()

    @staticmethod
    def _normalize_packet_type(packet_type):
        if isinstance(packet_type, bytes):
            try:
                return packet_type.decode(
                    "ascii"
                )

            except UnicodeDecodeError as exc:
                raise ProtocolError(
                    "invalid Soup packet type"
                ) from exc

        return packet_type