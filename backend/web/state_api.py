import copy
import socket
from datetime import datetime, timezone


PROTOCOL_NAMES = {
    "A": "API",
    "D": "DROP",
    "O": "OUCH",
    "I": "ITCH",
    "F": "FIX_ORDER_ENTRY",
    "C": "FIX_DROP_COPY",
    "M": "MARKET_DROP",
    "G": "GLIMPSE",
}

LOGON_STATE_NAMES = {0: "LOGGED_ON", 1: "LOGGED_OFF"}
STATE_NAMES = {"A": "ACTIVE", "S": "SUSPENDED", "D": "DELETED"}
USER_EVENT_NAMES = {0: "LOGON", 1: "LOGON_REJECTED", 2: "LOGOUT"}


class StateApiError(Exception):
    """State API operation failed."""


class StateUnavailableError(
    StateApiError
):
    """Live DROP state is temporarily unavailable."""

    def __init__(
        self,
        message=None,
        reason="drop_unavailable",
    ):
        self.reason = reason
        self.status_code = 503

        if message is None:
            message = (
                "DROP is not live. State data is "
                "temporarily unavailable."
            )

        super().__init__(message)


class StateNotFoundError(
    StateApiError
):
    """Requested state record was not found."""

    def __init__(
        self,
        entity_type,
        entity_id,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id

        super().__init__(
            "%s %r was not found"
            % (
                entity_type,
                entity_id,
            )
        )


class StateApi:
    """
    Read-only interface over live ApplicationState.

    Checkpoint-restored state remains available internally
    for DROP resume and reconciliation, but entity data is
    exposed only while DROP reports data_available=True.

    Returned values contain only dictionaries, lists,
    strings, numbers, booleans, and None, so they can be
    encoded directly as JSON by the HTTP layer.
    """

    def __init__(
        self,
        application_state,
        drop_service=None,
    ):
        if application_state is None:
            raise ValueError(
                "application state is required"
            )

        self.application_state = (
            application_state
        )
        self.drop_service = drop_service

    def health(self):
        """Return current backend and DROP readiness."""

        internal_counts = (
            self.application_state.counts()
        )

        if self.drop_service is None:
            return {
                "status": "ok",
                "drop_configured": False,
                "drop_service_running": None,
                "drop_running": None,
                "drop_connected": None,
                "drop_live": None,
                "connection_state": None,
                "state_ready": True,
                "data_available": True,
                "state_source": "memory",
                "drop_session": None,
                "last_packet_age_seconds": None,
                "last_error": None,
                "state_counts": internal_counts,
                "latest_event_id": (
                    self._latest_event_id()
                ),
            }

        service_status = (
            self.drop_service.status()
        )

        service_running = bool(
            service_status.get("running")
        )
        connected = bool(
            service_status.get("connected")
        )
        drop_live = bool(
            service_status.get("drop_live")
        )
        state_ready = bool(
            service_status.get("state_ready")
        )
        data_available = bool(
            service_status.get("data_available")
        )
        last_error = service_status.get(
            "last_error"
        )

        if data_available:
            health_status = "ok"
        elif service_running:
            health_status = "degraded"
        else:
            health_status = "error"

        state_source = self._state_source(
            service_status
        )

        return {
            "status": health_status,
            "drop_configured": True,

            # Keep the old field for frontend compatibility,
            # but make it mean usable live DROP availability.
            "drop_running": data_available,

            # New explicit fields remove ambiguity.
            "drop_service_running": service_running,
            "drop_connected": connected,
            "drop_live": drop_live,
            "connection_state": (
                service_status.get(
                    "connection_state"
                )
            ),
            "state_ready": state_ready,
            "data_available": data_available,
            "state_source": state_source,
            "drop_session": (
                service_status.get(
                    "current_session"
                )
            ),
            "last_packet_age_seconds": (
                service_status.get(
                    "last_packet_age_seconds"
                )
            ),
            "last_error": last_error,

            # Never publish checkpoint counts as live health
            # data while DROP is unavailable.
            "state_counts": (
                internal_counts
                if data_available
                else self._empty_counts()
            ),
            "latest_event_id": (
                self._latest_event_id()
            ),
        }

    def status(self):
        """
        Return detailed diagnostic status.

        Internal counts remain visible here for operations,
        but readiness and source clearly identify whether
        those counts are live or restored/stale.
        """

        internal_counts = (
            self.application_state.counts()
        )

        response = {
            "state": {
                "ready": (
                    self.drop_service is None
                ),
                "data_available": (
                    self.drop_service is None
                ),
                "source": (
                    "memory"
                    if self.drop_service is None
                    else "unavailable"
                ),
                "counts": internal_counts,
                "public_counts": internal_counts,
                "latest_event_id": (
                    self._latest_event_id()
                ),
            },
            "drop": None,
        }

        if self.drop_service is None:
            return response

        service_status = (
            self.drop_service.status()
        )

        state_ready = bool(
            service_status.get("state_ready")
        )
        data_available = bool(
            service_status.get("data_available")
        )
        state_source = self._state_source(
            service_status
        )

        response["state"].update(
            {
                "ready": state_ready,
                "data_available": data_available,
                "source": state_source,
                "public_counts": (
                    internal_counts
                    if data_available
                    else self._empty_counts()
                ),
            }
        )

        response["drop"] = {
            "running": bool(
                service_status.get("running")
            ),
            "connected": bool(
                service_status.get("connected")
            ),
            "connection_state": (
                service_status.get(
                    "connection_state"
                )
            ),
            "drop_live": bool(
                service_status.get("drop_live")
            ),
            "state_ready": state_ready,
            "data_available": data_available,
            "last_packet_age_seconds": (
                service_status.get(
                    "last_packet_age_seconds"
                )
            ),
            "liveness_timeout_seconds": (
                service_status.get(
                    "liveness_timeout_seconds"
                )
            ),
            "started": bool(
                service_status.get("started")
            ),
            "finished": bool(
                service_status.get("finished")
            ),
            "current_session": (
                service_status.get(
                    "current_session"
                )
            ),
            "requested_session": (
                service_status.get(
                    "requested_session"
                )
            ),
            "accepted_session": (
                service_status.get(
                    "accepted_session"
                )
            ),
            "requested_sequence": (
                service_status.get(
                    "requested_sequence"
                )
            ),
            "accepted_sequence": (
                service_status.get(
                    "accepted_sequence"
                )
            ),
            "next_soup_sequence": (
                service_status.get(
                    "next_soup_sequence"
                )
            ),
            "connections": (
                service_status.get(
                    "connections",
                    0,
                )
            ),
            "reconnects": (
                service_status.get(
                    "reconnects",
                    0,
                )
            ),
            "full_replay_fallbacks": (
                service_status.get(
                    "full_replay_fallbacks",
                    0,
                )
            ),
            "received_messages": (
                service_status.get(
                    "received_messages",
                    0,
                )
            ),
            "applied_messages": (
                service_status.get(
                    "applied_messages",
                    0,
                )
            ),
            "disconnect_reason": (
                service_status.get(
                    "disconnect_reason"
                )
            ),
            "unsupported_templates": (
                copy.deepcopy(
                    service_status.get(
                        "unsupported_templates",
                        [],
                    )
                )
            ),
            "last_error": (
                service_status.get(
                    "last_error"
                )
            ),
            "checkpoint": {
                "enabled": bool(
                    service_status.get(
                        "checkpoint_enabled"
                    )
                ),
                "restored": bool(
                    service_status.get(
                        "checkpoint_restored"
                    )
                ),
                "saves": (
                    service_status.get(
                        "checkpoint_saves",
                        0,
                    )
                ),
                "restored_trade_date": (
                    service_status.get(
                        "checkpoint_restored_trade_date"
                    )
                ),
                "restored_sequence": (
                    service_status.get(
                        "checkpoint_restored_sequence"
                    )
                ),
                "last_saved_at": (
                    service_status.get(
                        "checkpoint_last_saved_at"
                    )
                ),
                "last_error": (
                    service_status.get(
                        "checkpoint_last_error"
                    )
                ),
            },
        }

        return response

    def get_session(self):
        self._require_data_available()

        snapshot = (
            self.application_state.snapshot()
        )

        session = snapshot.get(
            "session"
        )

        if not isinstance(session, dict):
            raise StateApiError(
                "application session state "
                "is invalid"
            )

        return {
            "item": copy.deepcopy(
                session
            ),
            "latest_event_id": (
                self._latest_event_id()
            ),
        }

    def list_users(self):
        self._require_data_available()
        records = self._get_enriched_users()
        records.sort(key=lambda record: record.get("user_id"))
        return {
            "items": records,
            "count": len(records),
            "data_available": True,
            "latest_event_id": self._latest_event_id(),
        }

    def get_user(self, user_id):
        self._require_data_available()
        user_id = self._validate_id(user_id, "user ID")

        for record in self._get_enriched_users():
            if record.get("user_id") == user_id:
                return {
                    "item": record,
                    "data_available": True,
                    "latest_event_id": self._latest_event_id(),
                }

        raise StateNotFoundError(entity_type="user", entity_id=user_id)

    def list_firms(self):
        self._require_data_available()

        return self._list_records(
            section_name="firms",
            id_field="firm_id",
        )

    def get_firm(self, firm_id):
        self._require_data_available()

        firm_id = self._validate_id(
            firm_id,
            "firm ID",
        )

        return self._get_record(
            section_name="firms",
            id_field="firm_id",
            entity_type="firm",
            entity_id=firm_id,
        )

    def list_markets(self):
        self._require_data_available()

        return self._list_records(
            section_name="markets",
            id_field="market_id",
        )

    def get_market(self, market_id):
        self._require_data_available()

        market_id = self._validate_id(
            market_id,
            "market ID",
        )

        return self._get_record(
            section_name="markets",
            id_field="market_id",
            entity_type="market",
            entity_id=market_id,
        )

    def _get_enriched_users(self):
        snapshot = self.application_state.snapshot()
        users = self._snapshot_records(snapshot, "users")
        firms = self._snapshot_records(snapshot, "firms")
        entry_points = self._snapshot_records(snapshot, "entry_points", required=False)
        firms_by_id = {record.get("firm_id"): record for record in firms}
        entry_points_by_user = {}

        for record in entry_points:
            client_user_id = record.get("client_user_id")
            entry_points_by_user.setdefault(client_user_id, []).append(record)

        enriched = []
        for user in users:
            firm = firms_by_id.get(user.get("firm_id"))
            connection = self._select_entry_point(entry_points_by_user.get(user.get("user_id"), []))
            enriched.append(self._enrich_user(user, firm, connection))
        return enriched

    @classmethod
    def _enrich_user(cls, user, firm, connection):
        record = copy.deepcopy(user)
        user_state = record.get("state")
        firm_state = firm.get("state") if firm is not None else None
        protocol_code = connection.get("protocol") if connection is not None else None
        logon_status = connection.get("logon_status") if connection is not None else None
        last_logon_time_ns = connection.get("last_logon_time_ns") if connection is not None else None
        last_logoff_time_ns = connection.get("last_logoff_time_ns") if connection is not None else None

        record.update({
            "username": record.get("user_name"),
            "user_state": user_state,
            "user_state_name": STATE_NAMES.get(user_state),
            "firm_code": firm.get("firm_code") if firm is not None else None,
            "firm_state": firm_state,
            "firm_state_name": STATE_NAMES.get(firm_state),
            "user_logon_state": LOGON_STATE_NAMES.get(logon_status),
            "host_ip_address": cls._format_ipv4(connection.get("host_address") if connection is not None else None),
            "host_port": connection.get("host_port") if connection is not None else None,
            "client_ip_address": cls._format_ipv4(connection.get("client_ip_address") if connection is not None else None),
            "client_port": connection.get("client_port") if connection is not None else None,
            "protocol": PROTOCOL_NAMES.get(protocol_code, protocol_code),
            "protocol_code": protocol_code,
            "last_logon_time": cls._format_timestamp_ns(last_logon_time_ns),
            "last_logon_time_ns": last_logon_time_ns,
            "last_logoff_time": cls._format_timestamp_ns(last_logoff_time_ns),
            "last_logoff_time_ns": last_logoff_time_ns,
            "entry_point_index": connection.get("entry_point_index") if connection is not None else None,
            "logon_count": connection.get("logon_count") if connection is not None else None,
            "user_event": USER_EVENT_NAMES.get(connection.get("user_event_type")) if connection is not None else None,
        })
        return record

    @staticmethod
    def _select_entry_point(records):
        if not records:
            return None

        return max(records, key=lambda record: (
            1 if record.get("logon_status") == 0 else 0,
            1 if record.get("logon_status") is not None else 0,
            int(record.get("status_sequence") or 0),
            int(record.get("last_timestamp_ns") or 0),
            int(record.get("entry_point_index") or 0),
        ))

    @staticmethod
    def _snapshot_records(snapshot, section_name, required=True):
        records = snapshot.get(section_name)
        if records is None and not required:
            return []
        if not isinstance(records, list):
            raise StateApiError("application state section %s must be a list" % section_name)
        for record in records:
            if not isinstance(record, dict):
                raise StateApiError("application state section %s contains an invalid record" % section_name)
        return copy.deepcopy(records)

    @staticmethod
    def _format_ipv4(value):
        if value is None or value == 0:
            return None
        try:
            unsigned_value = int(value) & 0xFFFFFFFF
            return socket.inet_ntoa(unsigned_value.to_bytes(4, byteorder="little", signed=False))
        except (OverflowError, OSError, TypeError, ValueError):
            return None

    @staticmethod
    def _format_timestamp_ns(value):
        if value is None or value <= 0:
            return None
        seconds, nanoseconds = divmod(int(value), 1000000000)
        try:
            date_time = datetime.fromtimestamp(seconds, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        return "%s.%09dZ" % (date_time.strftime("%Y-%m-%dT%H:%M:%S"), nanoseconds)

    def _require_data_available(self):
        if self.drop_service is None:
            return

        service_status = (
            self.drop_service.status()
        )

        if service_status.get(
            "data_available"
        ):
            return

        connection_state = (
            service_status.get(
                "connection_state"
            )
        )

        if connection_state == "starting":
            raise StateUnavailableError(
                message=(
                    "DROP state initialization is "
                    "in progress."
                ),
                reason="state_initializing",
            )

        if connection_state == "stale":
            raise StateUnavailableError(
                message=(
                    "DROP connection is stale. State "
                    "data is temporarily unavailable."
                ),
                reason="drop_stale",
            )

        raise StateUnavailableError(
            message=(
                "DROP is not connected. State data "
                "is temporarily unavailable."
            ),
            reason="drop_unavailable",
        )

    def _list_records(
        self,
        section_name,
        id_field,
    ):
        records = self._get_section(
            section_name
        )

        records.sort(
            key=lambda record: (
                record.get(id_field)
            )
        )

        return {
            "items": records,
            "count": len(records),
            "data_available": True,
            "latest_event_id": (
                self._latest_event_id()
            ),
        }

    def _get_record(
        self,
        section_name,
        id_field,
        entity_type,
        entity_id,
    ):
        records = self._get_section(
            section_name
        )

        for record in records:
            if (
                record.get(id_field)
                == entity_id
            ):
                return {
                    "item": record,
                    "data_available": True,
                    "latest_event_id": (
                        self._latest_event_id()
                    ),
                }

        raise StateNotFoundError(
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def _get_section(
        self,
        section_name,
    ):
        snapshot = (
            self.application_state.snapshot()
        )

        records = snapshot.get(
            section_name
        )

        if not isinstance(records, list):
            raise StateApiError(
                "application state section %s "
                "must be a list"
                % section_name
            )

        for record in records:
            if not isinstance(record, dict):
                raise StateApiError(
                    "application state section %s "
                    "contains an invalid record"
                    % section_name
                )

        return copy.deepcopy(
            records
        )

    def _latest_event_id(self):
        event_bus = getattr(
            self.application_state,
            "event_bus",
            None,
        )

        if event_bus is None:
            return 0

        return event_bus.latest_event_id

    @staticmethod
    def _empty_counts():
        return {
            "users": 0,
            "firms": 0,
            "markets": 0,
            "entry_points": 0,
            "user_types": 0,
            "user_markets": 0,
            "system_events": 0,
        }

    @staticmethod
    def _state_source(
        service_status,
    ):
        if service_status.get(
            "data_available"
        ):
            return "live"

        if service_status.get(
            "checkpoint_restored"
        ):
            return "checkpoint"

        return "unavailable"

    @staticmethod
    def _validate_id(
        entity_id,
        description,
    ):
        if (
            not isinstance(entity_id, int)
            or isinstance(entity_id, bool)
        ):
            raise TypeError(
                "%s must be an integer"
                % description
            )

        if entity_id < 1:
            raise ValueError(
                "%s must be at least 1"
                % description
            )

        return entity_id
