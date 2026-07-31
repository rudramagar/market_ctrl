from flask import Flask, jsonify

from backend.web.state_api import (
    StateApiError,
    StateNotFoundError,
)


def create_http_app(state_api):
    """
    Create the HTTP application.

    All state reading remains inside StateApi. This
    layer only maps HTTP routes and status codes.
    """

    if state_api is None:
        raise ValueError(
            "state API is required"
        )

    app = Flask(__name__)

    app.config["JSON_SORT_KEYS"] = False

    @app.after_request
    def add_response_headers(response):
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
