import os


DEFAULT_CHECKPOINT_FILE = (
    "/data/market-control/current_session.json"
)

DEFAULT_CHECKPOINT_SAVE_INTERVAL_MESSAGES = 100

TRUE_VALUES = (
    "1",
    "true",
    "yes",
    "on",
)

FALSE_VALUES = (
    "0",
    "false",
    "no",
    "off",
)


class SettingsError(ValueError):
    """Application configuration is invalid."""


def get_drop_username():
    return _required_setting(
        names=(
            "MARKET_CONTROL_DROP_USERNAME",
            "DROP_USERNAME",
        ),
        description="DROP username",
    )


def get_drop_password():
    return _required_setting(
        names=(
            "MARKET_CONTROL_DROP_PASSWORD",
            "DROP_PASSWORD",
        ),
        description="DROP password",
    )


def get_api_username():
    return _required_setting(
        names=(
            "MARKET_CONTROL_API_USERNAME",
            "API_USERNAME",
        ),
        description="API username",
    )


def get_api_password():
    return _required_setting(
        names=(
            "MARKET_CONTROL_API_PASSWORD",
            "API_PASSWORD",
        ),
        description="API password",
    )


def get_checkpoint_file():
    """
    Return the current-session checkpoint path.

    Kubernetes should mount a writable persistent
    volume at /data/market-control.
    """

    value = _optional_setting(
        names=(
            "MARKET_CONTROL_CHECKPOINT_FILE",
        ),
        default=DEFAULT_CHECKPOINT_FILE,
    )

    value = os.path.abspath(
        os.path.expanduser(value)
    )

    if os.path.isdir(value):
        raise SettingsError(
            "checkpoint file points to a directory: %s"
            % value
        )

    return value


def get_checkpoint_save_interval_messages():
    """
    Return the number of decoded DROP messages
    between periodic checkpoint saves.

    Zero disables periodic saves. A checkpoint is
    still saved during clean shutdown.
    """

    return _integer_setting(
        name=(
            "MARKET_CONTROL_CHECKPOINT_"
            "SAVE_INTERVAL_MESSAGES"
        ),
        default=(
            DEFAULT_CHECKPOINT_SAVE_INTERVAL_MESSAGES
        ),
        minimum=0,
    )


def get_checkpoint_restore_enabled():
    """
    Return whether startup should restore an
    existing checkpoint.
    """

    return _boolean_setting(
        name=(
            "MARKET_CONTROL_CHECKPOINT_"
            "RESTORE_ENABLED"
        ),
        default=True,
    )


def get_checkpoint_save_on_shutdown():
    """
    Return whether a final checkpoint should be
    saved during service shutdown.
    """

    return _boolean_setting(
        name=(
            "MARKET_CONTROL_CHECKPOINT_"
            "SAVE_ON_SHUTDOWN"
        ),
        default=True,
    )


def _required_setting(
    names,
    description,
):
    for name in names:
        value = os.environ.get(name)

        if value is None:
            continue

        value = value.strip()

        if value:
            return value

    raise SettingsError(
        "%s is not configured; set one of: %s"
        % (
            description,
            ", ".join(names),
        )
    )


def _optional_setting(
    names,
    default=None,
):
    for name in names:
        value = os.environ.get(name)

        if value is None:
            continue

        value = value.strip()

        if value:
            return value

    return default


def _integer_setting(
    name,
    default,
    minimum=None,
):
    raw_value = os.environ.get(name)

    if raw_value is None:
        value = default

    else:
        raw_value = raw_value.strip()

        if not raw_value:
            value = default

        else:
            try:
                value = int(raw_value)

            except ValueError as exc:
                raise SettingsError(
                    "%s must be an integer: %r"
                    % (
                        name,
                        raw_value,
                    )
                ) from exc

    if (
        minimum is not None
        and value < minimum
    ):
        raise SettingsError(
            "%s must be at least %d"
            % (
                name,
                minimum,
            )
        )

    return value


def _boolean_setting(
    name,
    default,
):
    raw_value = os.environ.get(name)

    if raw_value is None:
        return bool(default)

    value = raw_value.strip().lower()

    if not value:
        return bool(default)

    if value in TRUE_VALUES:
        return True

    if value in FALSE_VALUES:
        return False

    raise SettingsError(
        "%s must be one of: %s"
        % (
            name,
            ", ".join(
                TRUE_VALUES
                + FALSE_VALUES
            ),
        )
    )
