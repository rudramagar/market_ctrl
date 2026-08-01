#!/usr/bin/env python3

import json
import os
import shutil
import tempfile

from backend.checkpoint.snapshot_store import (
    SnapshotFormatError,
    SnapshotStore,
)


def main():
    test_directory = tempfile.mkdtemp(
        prefix="market-control-snapshot-"
    )

    snapshot_path = os.path.join(
        test_directory,
        "current_session.json",
    )

    store = SnapshotStore(
        snapshot_path
    )

    try:
        print(
            "test directory: %s"
            % test_directory
        )

        if store.load() is not None:
            raise AssertionError(
                "new store must be empty"
            )

        first_snapshot = {
            "format_version": 1,
            "soup_session": "session-1",
            "next_soup_sequence": 100,
            "trade_date": 20260730,
            "state": {
                "users": [
                    {
                        "user_id": 402,
                        "state": "A",
                    }
                ]
            },
        }

        store.save(
            first_snapshot
        )

        loaded = store.load()

        if loaded != first_snapshot:
            raise AssertionError(
                "loaded snapshot does not "
                "match saved snapshot"
            )

        print(
            "initial save/load: PASSED"
        )

        second_snapshot = {
            "format_version": 1,
            "soup_session": "session-1",
            "next_soup_sequence": 200,
            "trade_date": 20260730,
            "state": {
                "users": [
                    {
                        "user_id": 402,
                        "state": "S",
                    }
                ]
            },
        }

        store.save(
            second_snapshot
        )

        loaded = store.load()

        if loaded != second_snapshot:
            raise AssertionError(
                "snapshot replacement failed"
            )

        print(
            "atomic replacement: PASSED"
        )

        temporary_files = [
            filename
            for filename in os.listdir(
                test_directory
            )
            if filename.endswith(
                ".tmp"
            )
        ]

        if temporary_files:
            raise AssertionError(
                "temporary files remain: %r"
                % temporary_files
            )

        print(
            "temporary cleanup: PASSED"
        )

        with open(
            snapshot_path,
            "w",
            encoding="utf-8",
        ) as snapshot_file:
            snapshot_file.write(
                "{invalid-json"
            )

        try:
            store.load()

        except SnapshotFormatError:
            print(
                "invalid JSON detection: PASSED"
            )

        else:
            raise AssertionError(
                "invalid JSON was accepted"
            )

        with open(
            snapshot_path,
            "w",
            encoding="utf-8",
        ) as snapshot_file:
            json.dump(
                second_snapshot,
                snapshot_file,
            )

        if not store.delete():
            raise AssertionError(
                "snapshot was not deleted"
            )

        if store.exists:
            raise AssertionError(
                "snapshot still exists"
            )

        if store.load() is not None:
            raise AssertionError(
                "deleted snapshot should "
                "load as None"
            )

        print(
            "delete: PASSED"
        )
        print(
            "snapshot store test: PASSED"
        )

        return 0

    finally:
        shutil.rmtree(
            test_directory,
            ignore_errors=True,
        )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
