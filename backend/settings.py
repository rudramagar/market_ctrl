import os

def get_required_setting(name):
    value = os.getenv(name)

    if not value:
        raise ValueError(
            "%s environment variable is required"
            % name
        )

    return value

def get_drop_username():
    return get_required_setting(
        "DROP_USERNAME"
    )

def get_drop_password():
    return get_required_setting(
        "DROP_PASSWORD"
    )
