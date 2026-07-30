import logging

from backend.protocol.drop.message_format import (
    DropMessageDecoder,
)
from backend.protocol.errors import (
    ConnectionClosedError,
    DropFormatError,
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
        decoder=None,
        strict_templates=False,
    ):
        if not host:
            raise ValueError("DROP host is required")

        if not username:
            raise ValueError("DROP username is required")

        if password is None:
            raise ValueError("DROP password is required")

        port = int(port)

        if port < 1 or port > 65535:
            raise ValueError(
                "invalid DROP port: %d" % port
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout_seconds = float(
            timeout_seconds
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

        self._next_sequence_number = None
        self._last_disconnect_reason = None
        self._unsupported_template_ids = set()

    @property
    def connected(self):
        return self._connected

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
        if self._connected:
            return

        sequence_number = int(sequence_number)

        if sequence_number < 1:
            raise ValueError(
                "sequence number must be at least 1"
            )

        tcp_socket = TcpSocket(
            self.host,
            self.port,
            timeout_seconds=self.timeout_seconds,
        )
        soup_session = SoupSession(tcp_socket)

        try:
            soup_session.connect()

            soup_session.login(
                self.username,
                self.password,
                session,
                sequence_number,
            )

        except Exception:
            soup_session.close()
            raise

        self._tcp_socket = tcp_socket
        self._soup_session = soup_session
        self._connected = True

        self._next_sequence_number = sequence_number
        self._last_disconnect_reason = None

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

            packet_type = self._normalize_packet_type(
                packet.packet_type
            )

            if packet_type == "H":
                self._soup_session.send_heartbeat()
                continue

            if packet_type == "Z":
                self._last_disconnect_reason = (
                    "end_of_session"
                )
                self._mark_disconnected()
                return None

            if packet_type != "S":
                logger.debug(
                    "ignored Soup packet type: %s",
                    packet_type,
                )
                continue

            self._advance_sequence()

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
        soup_session = self._soup_session
        was_connected = self._connected

        self._connected = False
        self._soup_session = None
        self._tcp_socket = None

        if soup_session is None:
            return

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

    def _advance_sequence(self):
        if self._next_sequence_number is None:
            raise ProtocolError(
                "Soup sequence is not initialized"
            )

        self._next_sequence_number += 1

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

    def _mark_disconnected(self):
        soup_session = self._soup_session

        self._connected = False
        self._soup_session = None
        self._tcp_socket = None

        if soup_session is not None:
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
