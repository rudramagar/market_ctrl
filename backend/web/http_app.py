import json

from flask import (
    Flask,
    Response,
    jsonify,
    request,
    stream_with_context,
)

from backend.events.state_event_bus import (
    StateEventHistoryGapError,
)
from backend.web.control_api import (
    ControlApiError,
    ControlNotFoundError,
    ControlRequestRejectedError,
    ControlRequestTimeoutError,
)
from backend.web.state_api import (
    StateApiError,
    StateNotFoundError,
    StateUnavailableError,
)
from backend.web.state_event_stream import (
    StateEventCursorError,
)


def create_http_app(
    state_api,
    state_event_stream=None,
    control_api=None,
):
    """
    Create the HTTP application.

    StateApi provides read-only state endpoints.
    StateEventStream provides live SSE updates.
    ControlApi provides state-change operations.
    """

    if state_api is None:
        raise ValueError(
            "state API is required"
        )

    app = Flask(__name__)

    app.config["JSON_SORT_KEYS"] = False

    @app.after_request
    def add_response_headers(response):
        if (
            response.mimetype
            == "text/event-stream"
        ):
            response.headers[
                "Cache-Control"
            ] = "no-cache"

            response.headers[
                "X-Accel-Buffering"
            ] = "no"

        else:
            response.headers[
                "Cache-Control"
            ] = "no-store"

        response.headers[
            "X-Content-Type-Options"
        ] = "nosniff"

        return response

    @app.route(
        "/health",
        methods=("GET",),
    )
    def health():
        payload = state_api.health()

        status_code = (
            200
            if payload.get("status") == "ok"
            else 503
        )

        return _json_response(
            payload,
            status_code,
        )

    @app.route(
        "/api/v1/status",
        methods=("GET",),
    )
    def status():
        return _json_response(
            state_api.status()
        )

    @app.route(
        "/api/v1/session",
        methods=("GET",),
    )
    def get_session():
        return _json_response(
            state_api.get_session()
        )

    @app.route(
        "/api/v1/users",
        methods=("GET",),
    )
    def list_users():
        return _json_response(
            state_api.list_users()
        )

    @app.route(
        "/api/v1/users/<int:user_id>",
        methods=("GET",),
    )
    def get_user(user_id):
        return _json_response(
            state_api.get_user(
                user_id
            )
        )

    @app.route(
        "/api/v1/firms",
        methods=("GET",),
    )
    def list_firms():
        return _json_response(
            state_api.list_firms()
        )

    @app.route(
        "/api/v1/firms/<int:firm_id>",
        methods=("GET",),
    )
    def get_firm(firm_id):
        return _json_response(
            state_api.get_firm(
                firm_id
            )
        )

    @app.route(
        "/api/v1/markets",
        methods=("GET",),
    )
    def list_markets():
        return _json_response(
            state_api.list_markets()
        )

    @app.route(
        "/api/v1/markets/<int:market_id>",
        methods=("GET",),
    )
    def get_market(market_id):
        return _json_response(
            state_api.get_market(
                market_id
            )
        )

    @app.route(
        "/api/v1/users/<int:user_id>/state",
        methods=("POST",),
    )
    def update_user_state(user_id):
        unavailable = (
            _control_unavailable_response(
                control_api
            )
        )

        if unavailable is not None:
            return unavailable

        control_request = (
            _parse_control_request()
        )

        result = (
            control_api.update_user_state(
                user_id=user_id,
                state=(
                    control_request["state"]
                ),
                timeout_seconds=(
                    control_request[
                        "timeout_seconds"
                    ]
                ),
            )
        )

        return _json_response(
            result
        )

    @app.route(
        "/api/v1/firms/<int:firm_id>/state",
        methods=("POST",),
    )
    def update_firm_state(firm_id):
        unavailable = (
            _control_unavailable_response(
                control_api
            )
        )

        if unavailable is not None:
            return unavailable

        control_request = (
            _parse_control_request()
        )

        result = (
            control_api.update_firm_state(
                firm_id=firm_id,
                state=(
                    control_request["state"]
                ),
                timeout_seconds=(
                    control_request[
                        "timeout_seconds"
                    ]
                ),
            )
        )

        return _json_response(
            result
        )

    @app.route(
        "/api/v1/markets/<int:market_id>/state",
        methods=("POST",),
    )
    def update_market_state(market_id):
        unavailable = (
            _control_unavailable_response(
                control_api
            )
        )

        if unavailable is not None:
            return unavailable

        control_request = (
            _parse_control_request()
        )

        result = (
            control_api.update_market_state(
                market_id=market_id,
                state=(
                    control_request["state"]
                ),
                timeout_seconds=(
                    control_request[
                        "timeout_seconds"
                    ]
                ),
            )
        )

        return _json_response(
            result
        )

    @app.route(
        "/api/v1/events",
        methods=("GET",),
    )
    def stream_events():
        if state_event_stream is None:
            return _json_response(
                {
                    "error": {
                        "code": (
                            "event_stream_unavailable"
                        ),
                        "message": (
                            "state event stream "
                            "is not configured"
                        ),
                    }
                },
                503,
            )

        after_event_id = (
            _get_after_event_id()
        )

        try:
            validated_event_id = (
                state_event_stream
                .validate_after_event_id(
                    after_event_id
                )
            )

        except StateEventHistoryGapError as exc:
            return _reset_event_response(
                reason="history_gap",
                requested_event_id=(
                    after_event_id
                ),
                latest_event_id=(
                    state_event_stream
                    .event_bus.latest_event_id
                ),
                oldest_event_id=(
                    exc.oldest_event_id
                ),
            )

        except StateEventCursorError as exc:
            return _reset_event_response(
                reason="cursor_ahead",
                requested_event_id=(
                    exc.requested_event_id
                ),
                latest_event_id=(
                    exc.latest_event_id
                ),
                oldest_event_id=(
                    state_event_stream
                    .event_bus.oldest_event_id
                ),
            )

        iterator = (
            state_event_stream.iter_events(
                after_event_id=(
                    validated_event_id
                )
            )
        )

        return Response(
            stream_with_context(
                iterator
            ),
            status=200,
            mimetype="text/event-stream",
        )

    @app.errorhandler(
        StateNotFoundError
    )
    def handle_state_not_found(error):
        return _json_response(
            {
                "error": {
                    "code": "not_found",
                    "message": str(error),
                    "entity_type": (
                        error.entity_type
                    ),
                    "entity_id": (
                        error.entity_id
                    ),
                }
            },
            404,
        )

    @app.errorhandler(
        ControlNotFoundError
    )
    def handle_control_not_found(error):
        return _json_response(
            {
                "error": {
                    "code": "not_found",
                    "message": str(error),
                    "entity_type": (
                        error.entity_type
                    ),
                    "entity_id": (
                        error.entity_id
                    ),
                }
            },
            404,
        )

    @app.errorhandler(
        StateUnavailableError
    )
    def handle_state_unavailable(error):
        return _json_response(
            {
                "error": {
                    "code": (
                        "state_unavailable"
                    ),
                    "message": str(error),
                    "reason": (
                        error.reason
                    ),
                }
            },
            503,
        )

    @app.errorhandler(
        StateApiError
    )
    def handle_state_api_error(error):
        return _json_response(
            {
                "error": {
                    "code": (
                        "state_api_error"
                    ),
                    "message": str(error),
                }
            },
            500,
        )

    @app.errorhandler(
        ControlRequestRejectedError
    )
    def handle_control_rejected(error):
        return _json_response(
            {
                "error": {
                    "code": "control_rejected",
                    "message": str(error),
                    "correlation_id": (
                        error.correlation_id
                    ),
                    "reject_reason": (
                        error.reject_reason
                    ),
                    "reject_text": (
                        error.reject_text
                    ),
                }
            },
            409,
        )

    @app.errorhandler(
        ControlRequestTimeoutError
    )
    def handle_control_timeout(error):
        return _json_response(
            {
                "error": {
                    "code": "control_timeout",
                    "message": str(error),
                }
            },
            504,
        )

    @app.errorhandler(
        ControlApiError
    )
    def handle_control_api_error(error):
        return _json_response(
            {
                "error": {
                    "code": (
                        "control_api_error"
                    ),
                    "message": str(error),
                }
            },
            502,
        )

    @app.errorhandler(ValueError)
    @app.errorhandler(TypeError)
    def handle_bad_request(error):
        return _json_response(
            {
                "error": {
                    "code": "bad_request",
                    "message": str(error),
                }
            },
            400,
        )

    @app.errorhandler(404)
    def handle_route_not_found(error):
        del error

        return _json_response(
            {
                "error": {
                    "code": "not_found",
                    "message": (
                        "HTTP route was not found"
                    ),
                }
            },
            404,
        )

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        del error

        return _json_response(
            {
                "error": {
                    "code": (
                        "method_not_allowed"
                    ),
                    "message": (
                        "HTTP method is not allowed"
                    ),
                }
            },
            405,
        )

    return app


def _parse_control_request():
    if not request.is_json:
        raise ValueError(
            "request content type must be "
            "application/json"
        )

    payload = request.get_json(
        silent=True
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "request body must be a valid "
            "JSON object"
        )

    allowed_fields = {
        "state",
        "timeout_seconds",
    }

    unknown_fields = (
        set(payload)
        - allowed_fields
    )

    if unknown_fields:
        raise ValueError(
            "unsupported request fields: %s"
            % ", ".join(
                sorted(
                    unknown_fields
                )
            )
        )

    if "state" not in payload:
        raise ValueError(
            "request body is missing state"
        )

    return {
        "state": payload["state"],
        "timeout_seconds": (
            payload.get(
                "timeout_seconds"
            )
        ),
    }


def _control_unavailable_response(
    control_api,
):
    if control_api is not None:
        return None

    return _json_response(
        {
            "error": {
                "code": (
                    "control_api_unavailable"
                ),
                "message": (
                    "control API is not configured"
                ),
            }
        },
        503,
    )


def _get_after_event_id():
    raw_value = request.args.get(
        "after_event_id"
    )

    if raw_value is None:
        raw_value = request.headers.get(
            "Last-Event-ID"
        )

    if raw_value is None:
        return None

    raw_value = raw_value.strip()

    if not raw_value:
        return None

    try:
        event_id = int(
            raw_value
        )

    except ValueError as exc:
        raise ValueError(
            "event cursor must be an integer"
        ) from exc

    if event_id < 0:
        raise ValueError(
            "event cursor cannot be negative"
        )

    return event_id


def _reset_event_response(
    reason,
    requested_event_id,
    latest_event_id,
    oldest_event_id,
):
    payload = {
        "reason": reason,
        "requested_event_id": (
            requested_event_id
        ),
        "latest_event_id": (
            latest_event_id
        ),
        "oldest_event_id": (
            oldest_event_id
        ),
    }

    data = json.dumps(
        payload,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    )

    body = (
        "id: %d\n"
        "event: reset\n"
        "data: %s\n"
        "\n"
        % (
            latest_event_id,
            data,
        )
    )

    return Response(
        body,
        status=200,
        mimetype="text/event-stream",
    )


def _json_response(
    payload,
    status_code=200,
):
    response = jsonify(
        payload
    )

    response.status_code = int(
        status_code
    )

    return response