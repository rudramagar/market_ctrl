#!/usr/bin/env python3

import os
import tempfile

from backend.settings import (
    DEFAULT_CHECKPOINT_FILE,
    SettingsError,
    get_api_password,
    get_api_username,
    get_checkpoint_file,
    get_checkpoint_restore_enabled,
    get_checkpoint_save_interval_messages,
    get_checkpoint_save_on_shutdown,
    get_drop_password,
    get_drop_username,
)


SETTING_NAMES = (
    "MARKET_CONTROL_DROP_USERNAME",
    "MARKET_CONTROL_DROP_PASSWORD",
    "MARKET_CONTROL_API_USERNAME",
    "MARKET_CONTROL_API_PASSWORD",
    "DROP_USERNAME",
    "DROP_PASSWORD",
    "API_USERNAME",
    "API_PASSWORD",
    "MARKET_CONTROL_CHECKPOINT_FILE",
    (
        "MARKET_CONTROL_CHECKPOINT_"
        "SAVE_INTERVAL_MESSAGES"
    ),
    (
        "MARKET_CONTROL_CHECKPOINT_"
        "RESTORE_ENABLED"
    ),
    (
        "MARKET_CONTROL_CHECKPOINT_"
        "SAVE_ON_SHUTDOWN"
    ),
)


def save_environment():
    return {
        name: os.environ.get(name)
        for name in SETTING_NAMES
    }


def restore_environment(saved):
    for name, value in saved.items():
        if value is None:
            os.environ.pop(
                name,
                None,
            )

        else:
            os.environ[name] = value


def clear_test_environment():
    for name in SETTING_NAMES:
        os.environ.pop(
            name,
            None,
        )


def test_credentials():
    os.environ["DROP_USERNAME"] = "drop01"
    os.environ["DROP_PASSWORD"] = "drop-password"
    os.environ["API_USERNAME"] = "api01"
    os.environ["API_PASSWORD"] = "api-password"

    if get_drop_username() != "drop01":
        raise AssertionError(
            "DROP username mismatch"
        )

    if (
        get_drop_password()
        != "drop-password"
    ):
        raise AssertionError(
            "DROP password mismatch"
        )

    if get_api_username() != "api01":
        raise AssertionError(
            "API username mismatch"
        )

    if (
        get_api_password()
        != "api-password"
    ):
        raise AssertionError(
            "API password mismatch"
        )

    os.environ[
        "MARKET_CONTROL_DROP_USERNAME"
    ] = "namespaced-drop"

    if (
        get_drop_username()
        != "namespaced-drop"
    ):
        raise AssertionError(
            "namespaced setting did not "
            "take priority"
        )

    print(
        "credential settings: PASSED"
    )


def test_missing_credentials():
    clear_test_environment()

    try:
        get_drop_username()

    except SettingsError:
        print(
            "missing credential detection: PASSED"
        )
        return

    raise AssertionError(
        "missing credential was not rejected"
    )


def test_checkpoint_defaults():
    clear_test_environment()

    expected_path = os.path.abspath(
        DEFAULT_CHECKPOINT_FILE
    )

    if get_checkpoint_file() != expected_path:
        raise AssertionError(
            "default checkpoint path mismatch"
        )

    if (
        get_checkpoint_save_interval_messages()
        != 100
    ):
        raise AssertionError(
            "default save interval mismatch"
        )

    if not get_checkpoint_restore_enabled():
        raise AssertionError(
            "checkpoint restore should default "
            "to enabled"
        )

    if not get_checkpoint_save_on_shutdown():
        raise AssertionError(
            "shutdown save should default "
            "to enabled"
        )

    print(
        "checkpoint defaults: PASSED"
    )


def test_checkpoint_overrides():
    temporary_directory = tempfile.mkdtemp(
        prefix="market-control-settings-"
    )

    checkpoint_path = os.path.join(
        temporary_directory,
        "checkpoint.json",
    )

    os.environ[
        "MARKET_CONTROL_CHECKPOINT_FILE"
    ] = checkpoint_path

    os.environ[
        "MARKET_CONTROL_CHECKPOINT_"
        "SAVE_INTERVAL_MESSAGES"
    ] = "25"

    os.environ[
        "MARKET_CONTROL_CHECKPOINT_"
        "RESTORE_ENABLED"
    ] = "false"

    os.environ[
        "MARKET_CONTROL_CHECKPOINT_"
        "SAVE_ON_SHUTDOWN"
    ] = "0"

    if (
        get_checkpoint_file()
        != os.path.abspath(checkpoint_path)
    ):
        raise AssertionError(
            "checkpoint path override mismatch"
        )

    if (
        get_checkpoint_save_interval_messages()
        != 25
    ):
        raise AssertionError(
            "checkpoint interval override mismatch"
        )

    if get_checkpoint_restore_enabled():
        raise AssertionError(
            "checkpoint restore override mismatch"
        )

    if get_checkpoint_save_on_shutdown():
        raise AssertionError(
            "shutdown save override mismatch"
        )

    print(
        "checkpoint overrides: PASSED"
    )


def test_invalid_checkpoint_settings():
    os.environ[
        "MARKET_CONTROL_CHECKPOINT_"
        "SAVE_INTERVAL_MESSAGES"
    ] = "-1"

    try:
        get_checkpoint_save_interval_messages()

    except SettingsError:
        pass

    else:
        raise AssertionError(
            "negative checkpoint interval "
            "was not rejected"
        )

    os.environ[
        "MARKET_CONTROL_CHECKPOINT_"
        "SAVE_INTERVAL_MESSAGES"
    ] = "100"

    os.environ[
        "MARKET_CONTROL_CHECKPOINT_"
        "RESTORE_ENABLED"
    ] = "maybe"

    try:
        get_checkpoint_restore_enabled()

    except SettingsError:
        pass

    else:
        raise AssertionError(
            "invalid boolean was not rejected"
        )

    print(
        "invalid checkpoint settings: PASSED"
    )


def main():
    saved_environment = save_environment()

    try:
        clear_test_environment()

        test_credentials()
        test_missing_credentials()
        test_checkpoint_defaults()
        test_checkpoint_overrides()
        test_invalid_checkpoint_settings()

        print(
            "settings test: PASSED"
        )

        return 0

    finally:
        restore_environment(
            saved_environment
        )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
