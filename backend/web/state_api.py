import copy


class StateApiError(Exception):
    """State API operation failed."""


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

    Returned values contain only dictionaries, lists,
    strings, numbers, booleans, and None, so they can
    be encoded directly as JSON by the HTTP layer.
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
        """
        Return a small health response.

        When no DROP service is supplied, only the
        state API itself is checked.
        """

        counts = (
            self.application_state.counts()
        )

        if self.drop_service is None:
            return {
                "status": "ok",
                "drop_configured": False,
                "drop_running": None,
                "drop_session": None,
                "last_error": None,
                "state_counts": counts,
                "latest_event_id": (
                    self._latest_event_id()
                ),
            }

        service_status = (
            self.drop_service.status()
        )

        healthy = (
            service_status["running"]
            and service_status["last_error"]
            is None
        )

        return {
            "status": (
                "ok"
                if healthy
                else "error"
            ),
            "drop_configured": True,
            "drop_running": (
                service_status["running"]
            ),
            "drop_session": (
                service_status[
                    "current_session"
                ]
            ),
            "last_error": (
                service_status["last_error"]
            ),
            "state_counts": counts,
            "latest_event_id": (
                self._latest_event_id()
            ),
        }

    def status(self):
        """
        Return detailed backend and state status.
        """

        response = {
            "state": {
                "counts": (
                    self.application_state
                    .counts()
                ),
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

        response["drop"] = {
            "running": (
                service_status["running"]
            ),
            "started": (
                service_status["started"]
            ),
            "finished": (
                service_status["finished"]
            ),
            "current_session": (
                service_status[
                    "current_session"
                ]
            ),
            "requested_session": (
                service_status[
                    "requested_session"
                ]
            ),
            "accepted_session": (
                service_status[
                    "accepted_session"
                ]
            ),
            "requested_sequence": (
                service_status[
                    "requested_sequence"
                ]
            ),
            "accepted_sequence": (
                service_status[
                    "accepted_sequence"
                ]
            ),
            "next_soup_sequence": (
                service_status[
                    "next_soup_sequence"
                ]
            ),
            "connections": (
                service_status["connections"]
            ),
            "reconnects": (
                service_status["reconnects"]
            ),
            "full_replay_fallbacks": (
                service_status[
                    "full_replay_fallbacks"
                ]
            ),
            "received_messages": (
                service_status[
                    "received_messages"
                ]
            ),
            "applied_messages": (
                service_status[
                    "applied_messages"
                ]
            ),
            "disconnect_reason": (
                service_status[
                    "disconnect_reason"
                ]
            ),
            "unsupported_templates": (
                copy.deepcopy(
                    service_status[
                        "unsupported_templates"
                    ]
                )
            ),
            "last_error": (
                service_status["last_error"]
            ),
            "checkpoint": {
                "enabled": (
                    service_status[
                        "checkpoint_enabled"
                    ]
                ),
                "restored": (
                    service_status[
                        "checkpoint_restored"
                    ]
                ),
                "saves": (
                    service_status[
                        "checkpoint_saves"
                    ]
                ),
                "restored_trade_date": (
                    service_status[
                        "checkpoint_restored_trade_date"
                    ]
                ),
                "restored_sequence": (
                    service_status[
                        "checkpoint_restored_sequence"
                    ]
                ),
                "last_saved_at": (
                    service_status[
                        "checkpoint_last_saved_at"
                    ]
                ),
                "last_error": (
                    service_status[
                        "checkpoint_last_error"
                    ]
                ),
            },
        }

        return response

    def get_session(self):
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
        return self._list_records(
            section_name="users",
            id_field="user_id",
        )

    def get_user(self, user_id):
        user_id = self._validate_id(
            user_id,
            "user ID",
        )

        return self._get_record(
            section_name="users",
            id_field="user_id",
            entity_type="user",
            entity_id=user_id,
        )

    def list_firms(self):
        return self._list_records(
            section_name="firms",
            id_field="firm_id",
        )

    def get_firm(self, firm_id):
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
        return self._list_records(
            section_name="markets",
            id_field="market_id",
        )

    def get_market(self, market_id):
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
