from datetime import datetime

from backend.checkpoint.snapshot_store import (
    SnapshotFormatError,
    SnapshotStoreError,
)


CHECKPOINT_FORMAT_VERSION = 1

CHECKPOINT_STATE_SECTIONS = (
    "users",
    "firms",
    "markets",
    "references",
    "session",
)


class SessionCheckpointError(Exception):
    """Session checkpoint operation failed."""


class SessionCheckpointFormatError(
    SessionCheckpointError
):
    """Session checkpoint contains invalid data."""


class SessionCheckpoint:
    """
    Save and restore one current-session checkpoint.

    The checkpoint contains:

    - Soup session
    - Next Soup sequence
    - Business trade date
    - Save timestamp
    - Complete ApplicationState snapshot
    """

    def __init__(
        self,
        snapshot_store,
        application_state,
    ):
        if snapshot_store is None:
            raise ValueError(
                "snapshot store is required"
            )

        if application_state is None:
            raise ValueError(
                "application state is required"
            )

        self.snapshot_store = snapshot_store
        self.application_state = (
            application_state
        )

    @property
    def exists(self):
        return self.snapshot_store.exists

    def build(
        self,
        soup_session,
        next_soup_sequence,
    ):
        """
        Build a checkpoint from current application state.

        This does not write anything to disk.
        """

        soup_session = self._validate_session(
            soup_session
        )
        next_soup_sequence = (
            self._validate_sequence(
                next_soup_sequence
            )
        )

        state_snapshot = (
            self.application_state.snapshot()
        )

        trade_date = (
            self.application_state
            .session
            .trade_date
        )

        trade_date = self._validate_trade_date(
            trade_date
        )

        checkpoint = {
            "format_version": (
                CHECKPOINT_FORMAT_VERSION
            ),
            "soup_session": soup_session,
            "next_soup_sequence": (
                next_soup_sequence
            ),
            "trade_date": trade_date,
            "saved_at": self._utc_now_text(),
            "state": state_snapshot,
        }

        return self.validate(checkpoint)

    def save(
        self,
        soup_session,
        next_soup_sequence,
    ):
        """
        Build and atomically save the current checkpoint.

        Returns the saved checkpoint dictionary.
        """

        checkpoint = self.build(
            soup_session=soup_session,
            next_soup_sequence=(
                next_soup_sequence
            ),
        )

        try:
            self.snapshot_store.save(
                checkpoint
            )

        except SnapshotStoreError as exc:
            raise SessionCheckpointError(
                "failed to save session checkpoint: %s"
                % exc
            ) from exc

        return checkpoint

    def load(self):
        """
        Load and validate the saved checkpoint.

        Returns None when no checkpoint exists.
        """

        try:
            checkpoint = (
                self.snapshot_store.load()
            )

        except SnapshotFormatError as exc:
            raise SessionCheckpointFormatError(
                "checkpoint file contains "
                "invalid JSON"
            ) from exc

        except SnapshotStoreError as exc:
            raise SessionCheckpointError(
                "failed to load session checkpoint: %s"
                % exc
            ) from exc

        if checkpoint is None:
            return None

        return self.validate(checkpoint)

    def restore(self):
        """
        Restore ApplicationState from the saved checkpoint.

        Returns checkpoint metadata and restored counts.
        Returns None when no checkpoint exists.
        """

        checkpoint = self.load()

        if checkpoint is None:
            return None

        try:
            restored_counts = (
                self.application_state.restore(
                    checkpoint["state"]
                )
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise SessionCheckpointFormatError(
                "failed to restore checkpoint state: %s"
                % exc
            ) from exc

        return {
            "format_version": (
                checkpoint["format_version"]
            ),
            "soup_session": (
                checkpoint["soup_session"]
            ),
            "next_soup_sequence": (
                checkpoint[
                    "next_soup_sequence"
                ]
            ),
            "trade_date": (
                checkpoint["trade_date"]
            ),
            "saved_at": (
                checkpoint["saved_at"]
            ),
            "restored_counts": (
                restored_counts
            ),
        }

    def delete(self):
        """Delete the saved checkpoint."""

        try:
            return self.snapshot_store.delete()

        except SnapshotStoreError as exc:
            raise SessionCheckpointError(
                "failed to delete session checkpoint: %s"
                % exc
            ) from exc

    def validate(self, checkpoint):
        """
        Validate and return a checkpoint dictionary.

        No application state is modified here.
        """

        if not isinstance(checkpoint, dict):
            raise SessionCheckpointFormatError(
                "checkpoint root must be an object"
            )

        required_fields = (
            "format_version",
            "soup_session",
            "next_soup_sequence",
            "trade_date",
            "saved_at",
            "state",
        )

        for field_name in required_fields:
            if field_name not in checkpoint:
                raise SessionCheckpointFormatError(
                    "checkpoint is missing %s"
                    % field_name
                )

        format_version = checkpoint[
            "format_version"
        ]

        if (
            not isinstance(format_version, int)
            or isinstance(format_version, bool)
        ):
            raise SessionCheckpointFormatError(
                "format_version must be an integer"
            )

        if (
            format_version
            != CHECKPOINT_FORMAT_VERSION
        ):
            raise SessionCheckpointFormatError(
                "unsupported checkpoint format: %d"
                % format_version
            )

        soup_session = self._validate_session(
            checkpoint["soup_session"],
            error_type=(
                SessionCheckpointFormatError
            ),
        )

        next_soup_sequence = (
            self._validate_sequence(
                checkpoint[
                    "next_soup_sequence"
                ],
                error_type=(
                    SessionCheckpointFormatError
                ),
            )
        )

        trade_date = self._validate_trade_date(
            checkpoint["trade_date"],
            error_type=(
                SessionCheckpointFormatError
            ),
        )

        saved_at = checkpoint["saved_at"]

        if not isinstance(saved_at, str):
            raise SessionCheckpointFormatError(
                "saved_at must be a string"
            )

        try:
            datetime.strptime(
                saved_at,
                "%Y-%m-%dT%H:%M:%S.%fZ",
            )

        except ValueError as exc:
            raise SessionCheckpointFormatError(
                "saved_at has an invalid format: %r"
                % saved_at
            ) from exc

        state = checkpoint["state"]

        if not isinstance(state, dict):
            raise SessionCheckpointFormatError(
                "checkpoint state must be an object"
            )

        for section_name in (
            CHECKPOINT_STATE_SECTIONS
        ):
            if section_name not in state:
                raise SessionCheckpointFormatError(
                    "checkpoint state is missing %s"
                    % section_name
                )

        state_trade_date = (
            self._extract_state_trade_date(
                state
            )
        )

        if state_trade_date is None:
            raise SessionCheckpointFormatError(
                "checkpoint state does not contain "
                "a trade date"
            )

        if state_trade_date != trade_date:
            raise SessionCheckpointFormatError(
                "checkpoint trade date mismatch: "
                "metadata=%d state=%d"
                % (
                    trade_date,
                    state_trade_date,
                )
            )

        return {
            "format_version": format_version,
            "soup_session": soup_session,
            "next_soup_sequence": (
                next_soup_sequence
            ),
            "trade_date": trade_date,
            "saved_at": saved_at,
            "state": state,
        }

    @staticmethod
    def _validate_session(
        soup_session,
        error_type=ValueError,
    ):
        if not isinstance(soup_session, str):
            raise error_type(
                "Soup session must be a string"
            )

        if not soup_session:
            raise error_type(
                "Soup session cannot be empty"
            )

        return soup_session

    @staticmethod
    def _validate_sequence(
        next_soup_sequence,
        error_type=ValueError,
    ):
        if (
            not isinstance(
                next_soup_sequence,
                int,
            )
            or isinstance(
                next_soup_sequence,
                bool,
            )
        ):
            raise error_type(
                "next Soup sequence must "
                "be an integer"
            )

        if next_soup_sequence < 1:
            raise error_type(
                "next Soup sequence must "
                "be at least 1"
            )

        return next_soup_sequence

    @staticmethod
    def _validate_trade_date(
        trade_date,
        error_type=ValueError,
    ):
        if (
            not isinstance(trade_date, int)
            or isinstance(trade_date, bool)
        ):
            raise error_type(
                "trade date must be an integer"
            )

        try:
            datetime.strptime(
                str(trade_date),
                "%Y%m%d",
            )

        except ValueError as exc:
            raise error_type(
                "invalid trade date: %r"
                % trade_date
            ) from exc

        return trade_date

    @staticmethod
    def _extract_state_trade_date(
        state,
    ):
        session_state = state.get(
            "session"
        )

        if not isinstance(
            session_state,
            dict,
        ):
            return None

        trade_date_record = (
            session_state.get(
                "trade_date"
            )
        )

        if isinstance(
            trade_date_record,
            dict,
        ):
            trade_date = (
                trade_date_record.get(
                    "trade_date"
                )
            )

            if (
                isinstance(trade_date, int)
                and not isinstance(
                    trade_date,
                    bool,
                )
            ):
                return trade_date

        trading_engine = (
            session_state.get(
                "trading_engine"
            )
        )

        if isinstance(
            trading_engine,
            dict,
        ):
            trade_date = (
                trading_engine.get(
                    "trade_date"
                )
            )

            if (
                isinstance(trade_date, int)
                and not isinstance(
                    trade_date,
                    bool,
                )
            ):
                return trade_date

        return None

    @staticmethod
    def _utc_now_text():
        return datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
