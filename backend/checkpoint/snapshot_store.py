import json
import os
import tempfile
from threading import RLock


class SnapshotStoreError(Exception):
    """Snapshot persistence operation failed."""


class SnapshotFormatError(
    SnapshotStoreError
):
    """Snapshot file contains invalid data."""


class SnapshotStore:
    """
    Atomically store one JSON snapshot.

    The snapshot is written to a temporary file,
    flushed to disk, and then moved over the current
    file using os.replace().
    """

    def __init__(
        self,
        path,
        file_mode=0o600,
    ):
        if not path:
            raise ValueError(
                "snapshot path is required"
            )

        self.path = os.path.abspath(path)
        self.directory = os.path.dirname(
            self.path
        )
        self.filename = os.path.basename(
            self.path
        )
        self.file_mode = int(file_mode)

        self._lock = RLock()

    @property
    def exists(self):
        with self._lock:
            return os.path.isfile(
                self.path
            )

    def save(self, snapshot):
        """
        Atomically save a snapshot dictionary.

        Returns the final snapshot path.
        """

        if not isinstance(snapshot, dict):
            raise SnapshotFormatError(
                "snapshot must be a dictionary"
            )

        with self._lock:
            self._ensure_directory()

            temporary_path = None

            try:
                file_descriptor, temporary_path = (
                    tempfile.mkstemp(
                        prefix=(
                            self.filename + "."
                        ),
                        suffix=".tmp",
                        dir=self.directory,
                    )
                )

                try:
                    os.chmod(
                        temporary_path,
                        self.file_mode,
                    )

                    with os.fdopen(
                        file_descriptor,
                        "w",
                        encoding="utf-8",
                    ) as snapshot_file:
                        json.dump(
                            snapshot,
                            snapshot_file,
                            ensure_ascii=False,
                            sort_keys=True,
                            indent=2,
                        )

                        snapshot_file.write(
                            "\n"
                        )
                        snapshot_file.flush()

                        os.fsync(
                            snapshot_file.fileno()
                        )

                except Exception:
                    try:
                        os.close(
                            file_descriptor
                        )

                    except OSError:
                        pass

                    raise

                os.replace(
                    temporary_path,
                    self.path,
                )

                temporary_path = None

                self._sync_directory()

                return self.path

            except (
                OSError,
                TypeError,
                ValueError,
            ) as exc:
                raise SnapshotStoreError(
                    "failed to save snapshot %s: %s"
                    % (
                        self.path,
                        exc,
                    )
                ) from exc

            finally:
                if (
                    temporary_path is not None
                    and os.path.exists(
                        temporary_path
                    )
                ):
                    try:
                        os.unlink(
                            temporary_path
                        )

                    except OSError:
                        pass

    def load(self):
        """
        Load the current snapshot.

        Returns None when the snapshot file does not
        exist.
        """

        with self._lock:
            if not os.path.exists(
                self.path
            ):
                return None

            if not os.path.isfile(
                self.path
            ):
                raise SnapshotStoreError(
                    "snapshot path is not a file: %s"
                    % self.path
                )

            try:
                with open(
                    self.path,
                    "r",
                    encoding="utf-8",
                ) as snapshot_file:
                    snapshot = json.load(
                        snapshot_file
                    )

            except json.JSONDecodeError as exc:
                raise SnapshotFormatError(
                    "snapshot contains invalid JSON: "
                    "%s"
                    % self.path
                ) from exc

            except OSError as exc:
                raise SnapshotStoreError(
                    "failed to load snapshot %s: %s"
                    % (
                        self.path,
                        exc,
                    )
                ) from exc

            if not isinstance(
                snapshot,
                dict,
            ):
                raise SnapshotFormatError(
                    "snapshot root must be an object"
                )

            return snapshot

    def delete(self):
        """
        Delete the current snapshot.

        Returns True when a file was deleted.
        """

        with self._lock:
            if not os.path.exists(
                self.path
            ):
                return False

            try:
                os.unlink(
                    self.path
                )
                self._sync_directory()

            except OSError as exc:
                raise SnapshotStoreError(
                    "failed to delete snapshot %s: %s"
                    % (
                        self.path,
                        exc,
                    )
                ) from exc

            return True

    def _ensure_directory(self):
        try:
            os.makedirs(
                self.directory,
                exist_ok=True,
            )

        except OSError as exc:
            raise SnapshotStoreError(
                "failed to create snapshot "
                "directory %s: %s"
                % (
                    self.directory,
                    exc,
                )
            ) from exc

        if not os.path.isdir(
            self.directory
        ):
            raise SnapshotStoreError(
                "snapshot directory is not "
                "a directory: %s"
                % self.directory
            )

    def _sync_directory(self):
        """
        Flush directory metadata after replace/delete.

        This is supported on Linux. Failure is ignored
        only when the platform does not support opening
        directories for fsync.
        """

        flags = os.O_RDONLY

        if hasattr(
            os,
            "O_DIRECTORY",
        ):
            flags |= os.O_DIRECTORY

        directory_descriptor = None

        try:
            directory_descriptor = os.open(
                self.directory,
                flags,
            )

            os.fsync(
                directory_descriptor
            )

        except OSError:
            # Some non-Linux filesystems do not permit
            # fsync on a directory.
            pass

        finally:
            if directory_descriptor is not None:
                os.close(
                    directory_descriptor
                )
