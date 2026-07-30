# Market Control Backend — Production Implementation Plan

## 1. Project Purpose

The Market Control backend provides a web-based interface for controlling market entities through the Mercury API.

The backend must support operations such as:

* Suspend or activate a user
* Suspend or activate a firm
* Suspend or activate a market
* Display the current state of users, firms, and markets
* Confirm API control requests through the DROP feed
* Recover safely from TCP disconnects and Kubernetes pod restarts
* Continue from the correct SoupBinTCP sequence during the same business session

The backend is a real-time operational application for the current market session. It is not intended to store historical market data or previous business-day state.

---

# 2. Final Architecture

```text
Browser / Frontend
        │
        ▼
REST API and WebSocket/SSE
        │
        ├── Read current application state
        │
        └── Submit control request
                     │
                     ▼
              ControlService
              │           │
              │           └── ApiClient
              │                 │
              │                 ▼
              │          Mercury API SoupBinTCP
              │
              └── Wait for DROP confirmation
                              │
                              ▼
                     DropStateService
                              │
                              ▼
                     DROP SoupBinTCP server
                              │
                              ▼
                     ApplicationState
                     ├── users
                     ├── firms
                     └── markets
                              │
                              ▼
                 SnapshotPersistenceService
                              │
                              ▼
                  Kubernetes ReadWriteOnce PVC
                  current_session.json
```

---

# 3. Important Architecture Decisions

## 3.1 No PostgreSQL

PostgreSQL is not required for the current application.

The backend only needs to preserve the current session state so it can recover after a pod restart.

The application does not require:

* Historical queries
* Previous-day state
* Full event history
* Multi-day state retention
* Relational reporting
* Multiple database users
* Complex transactions across many business entities

## 3.2 No Redis

Redis is also not required.

The application will use:

```text
In-memory ApplicationState
+
Kubernetes PersistentVolumeClaim
+
one atomic JSON snapshot
```

## 3.3 One Active Backend Pod

The initial production deployment will use one backend replica:

```yaml
replicaCount: 1
```

Only one process should own:

* The DROP SoupBinTCP session
* The Mercury API SoupBinTCP session
* The in-memory application state
* The runtime snapshot file

Multiple active replicas could cause:

* Duplicate DROP logins
* Duplicate API sessions
* Conflicting snapshots
* Duplicate control requests
* Inconsistent in-memory state

High availability can be added later using leader election or by separating the ingestion worker from the REST API.

---

# 4. Protocol Flow

## 4.1 Startup from Sequence 1

When there is no valid current-session snapshot:

```text
Backend starts
    ↓
Clear ApplicationState
    ↓
Connect to DROP from Soup sequence 1
    ↓
Receive the initial replay
    ↓
Build users, firms, and markets
    ↓
Track the next Soup sequence
    ↓
Persist a current-session snapshot
    ↓
Reconnect or remain connected for live updates
```

## 4.2 Live Operation

```text
Receive Soup S packet
    ↓
Advance next Soup sequence
    ↓
Decode DROP message
    ↓
Apply supported state update
    ↓
Notify waiting ControlService requests
    ↓
Mark persistence state dirty
    ↓
Continue waiting for the next packet
```

The DROP receive call remains blocked while waiting for live messages. There is no frontend polling of the DROP server.

## 4.3 TCP Disconnect During the Same Process

If the DROP TCP connection closes while the backend process is still running:

```text
TCP connection closes
    ↓
Keep ApplicationState in memory
    ↓
Keep next Soup sequence in memory
    ↓
Wait for reconnect delay
    ↓
Reconnect from the next Soup sequence
    ↓
Replay only missed messages
    ↓
Continue live listening
```

The state must not be cleared during a reconnect.

## 4.4 Kubernetes Pod Restart During the Same Session

If the pod restarts, memory is lost.

The backend must:

```text
Pod starts
    ↓
Load current_session.json from PVC
    ↓
Validate the snapshot
    ↓
Restore users, firms, and markets
    ↓
Read saved next Soup sequence
    ↓
Reconnect from that sequence
    ↓
Replay messages received after the snapshot
    ↓
Continue live listening
```

The backend must not restart from sequence `1` when a valid same-session snapshot exists.

---

# 5. Control Request Flow

A control request is not considered successful only because the API message was sent.

It is successful only after the corresponding DROP state update is received.

```text
Frontend sends control request
    ↓
Backend validates request
    ↓
ControlService reads current entity state
    ↓
Record current matching-engine sequence
    ↓
ApiClient sends control request
    ↓
ApiClient returns correlation ID
    ↓
ControlService waits for DROP
    ↓
DROP receives a newer matching state update
    ↓
ApplicationState updates the entity
    ↓
ControlService returns confirmed result
```

Example:

```text
User 402 current state: A
    ↓
Send Update User State: S
    ↓
API correlation ID returned
    ↓
Receive DROP UserStatus: S
    ↓
Matching-engine sequence is newer
    ↓
Request confirmed
```

A previous state already stored in memory must not be accepted as confirmation.

Confirmation requires:

```text
record.state == requested_state
and
record.last_sequence > sequence_before_request
```

---

# 6. Persistence Design

## 6.1 Persistent Storage

Use one Kubernetes `ReadWriteOnce` PersistentVolumeClaim.

Recommended mount path:

```text
/data/market-control
```

Recommended snapshot path:

```text
/data/market-control/current_session.json
```

A storage request of `1Gi` is more than sufficient.

## 6.2 Snapshot Contents

The snapshot stores only:

* Snapshot schema version
* Business date
* Soup session identifier
* Session status
* Next Soup sequence
* Snapshot creation timestamp
* Latest user state
* Latest firm state
* Latest market state

Example:

```json
{
  "version": 1,
  "business_date": "2026-07-30",
  "soup_session": "",
  "status": "ACTIVE",
  "next_soup_sequence": 9107,
  "saved_at": "2026-07-30T17:40:00+09:00",
  "users": {
    "402": {
      "user_id": 402,
      "name": "TX99900C",
      "firm_id": 2,
      "state": "A",
      "definition_sequence": 8790,
      "state_sequence": 8888,
      "last_sequence": 8888,
      "last_timestamp_ns": 1785398734364416
    }
  },
  "firms": {
    "2": {
      "firm_id": 2,
      "code": "00099900",
      "name": "Japannext co., ltd. Internal QA.",
      "firm_type": "B",
      "state": "A",
      "last_sequence": 8838
    }
  },
  "markets": {
    "16": {
      "market_id": 16,
      "name": "XNET",
      "state": "A",
      "trading_session": 0,
      "last_sequence": 8738
    }
  }
}
```

## 6.3 Data That Must Not Be Persisted

The backend must not store:

* Every DROP message
* Full intraday DROP history
* Heartbeats
* Every entity state transition
* Unsupported message payloads
* Full market data
* Trades
* Orders
* Order books
* Previous business-day runtime state
* Multiple snapshots from the same day

For example, if user `402` changes:

```text
A → S → A → S → A
```

the snapshot stores only the latest state:

```text
user 402 state=A
```

## 6.4 Constant File Size

The same snapshot file is replaced throughout the session.

```text
current_session.json
    ↓
new consistent state created in memory
    ↓
write temporary snapshot
    ↓
atomically replace current_session.json
```

The file does not grow throughout the day.

Its approximate size depends only on the number of users, firms, and markets—not the number of messages received.

---

# 7. Atomic File Writing

The active snapshot file must never be modified directly.

Use this flow:

```text
Write current_session.json.tmp
    ↓
flush file buffer
    ↓
fsync file
    ↓
close temporary file
    ↓
os.replace temporary file with active file
    ↓
fsync parent directory
```

Example implementation behavior:

```python
temporary_path = snapshot_path + ".tmp"

with open(temporary_path, "w") as snapshot_file:
    json.dump(snapshot, snapshot_file)
    snapshot_file.flush()
    os.fsync(snapshot_file.fileno())

os.replace(
    temporary_path,
    snapshot_path,
)
```

Atomic replacement prevents a pod crash from leaving a partially written active snapshot.

---

# 8. Snapshot Consistency Rule

The persisted application state and the persisted next Soup sequence must represent the same point in the stream.

Unsafe example:

```text
ApplicationState includes messages through Soup sequence 9180
Persisted next Soup sequence is 9200
```

After restart, requesting `9200` would skip messages `9180` through `9199`.

Correct snapshot:

```text
ApplicationState includes all required state updates before sequence 9180
Persisted next Soup sequence is 9180
```

The snapshot must be copied from a consistent in-memory view.

The state snapshot and checkpoint must be written together as one JSON document.

---

# 9. Persistence Frequency

The backend should not write to the PVC for every DROP packet.

Recommended persistence policy:

```text
State changes:
    mark snapshot dirty

Periodic worker:
    save every 2–5 seconds when dirty

Soup packets without supported state changes:
    save checkpoint periodically

Confirmed control request:
    save immediately

Graceful shutdown:
    save immediately

End of session:
    save immediately
```

A reasonable first implementation:

```text
snapshot_interval_seconds = 5
```

The persistence worker should:

1. Check whether state or sequence changed.
2. Capture a consistent snapshot.
3. Write the snapshot atomically.
4. Mark the snapshot clean.
5. Wait for the next interval.

---

# 10. Crash Recovery Model

The recovery model should be at least once.

Example:

```text
Persisted next sequence: 9200
In-memory next sequence: 9210
Pod crashes
```

After restart:

```text
Restore snapshot at sequence 9200
    ↓
Request Soup sequence 9200
    ↓
Replay packets 9200 through 9209 again
    ↓
Continue live
```

Replaying a small number of packets is safer than skipping packets.

State stores must therefore safely ignore stale or duplicate updates.

Example rule:

```python
if incoming_sequence <= record.last_sequence:
    return False
```

The exact duplicate-protection rule may need to consider separate definition and state sequences for each entity type.

---

# 11. Session Lifecycle

## 11.1 Current Session Only

The backend retains only the current session snapshot.

It does not retain yesterday’s runtime state.

## 11.2 Snapshot Status

Supported snapshot statuses:

```text
ACTIVE
COMPLETED
```

Optional future statuses:

```text
INITIALIZING
INVALID
```

## 11.3 End-of-Session

The Soup `Z` End-of-Session message should be the primary session-completion signal.

```text
Receive Soup Z
    ↓
Stop reconnecting to the completed session
    ↓
Capture final consistent snapshot
    ↓
Set snapshot status to COMPLETED
    ↓
Save snapshot immediately
```

## 11.4 Next Business Session

When the next session begins:

```text
Read current_session.json
    ↓
Snapshot is from a previous business date or previous Soup session
    ↓
Do not restore it
    ↓
Remove or replace the snapshot
    ↓
Clear ApplicationState
    ↓
Connect from sequence 1
    ↓
Build new session state
    ↓
Save new ACTIVE snapshot
```

Previous-session data is deleted or overwritten when the new session is initialized.

## 11.5 No Daily PVC Deletion

Do not delete or recreate the Kubernetes PersistentVolumeClaim every day.

Correct cleanup:

```text
Replace or delete current_session.json
```

Incorrect cleanup:

```text
Delete the PVC
Recreate the PVC
Recreate the storage
```

The PVC remains attached to the application. Only its current-session snapshot is replaced.

---

# 12. Session Validation

A saved snapshot may be restored only when it matches the current expected session.

Validation should include:

* Supported snapshot schema version
* Valid JSON structure
* Required fields are present
* Snapshot status is `ACTIVE`
* Business date matches
* Soup session identifier matches
* Next Soup sequence is greater than or equal to `1`
* Users, firms, and markets are valid collections
* Entity records contain required fields
* No invalid state values are present

Restore flow:

```text
Valid ACTIVE snapshot for the current session
    → restore state
    → resume from saved sequence
```

Fallback flow:

```text
Missing, stale, completed, or invalid snapshot
    → clear state
    → start from sequence 1
```

---

# 13. Corrupted Snapshot Handling

A corrupted snapshot must not prevent safe startup.

```text
Snapshot cannot be decoded or validated
    ↓
Log validation failure
    ↓
Rename file to current_session.invalid
    ↓
Clear ApplicationState
    ↓
Connect from sequence 1
    ↓
Perform full reconstruction
```

Do not resume from a checkpoint when its matching state cannot be restored.

Possible invalid file name:

```text
current_session.invalid
```

Only one invalid snapshot needs to be retained temporarily for troubleshooting. It can be replaced by the next invalid file or removed after investigation.

---

# 14. Kubernetes Persistence Configuration

## 14.1 PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: market-control-state
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

The final storage class should be selected according to the Kubernetes environment.

## 14.2 Deployment Volume Mount

```yaml
volumeMounts:
  - name: runtime-state
    mountPath: /data/market-control

volumes:
  - name: runtime-state
    persistentVolumeClaim:
      claimName: market-control-state
```

## 14.3 Replica Count

```yaml
replicaCount: 1
```

## 14.4 Graceful Shutdown

The pod must receive enough termination time to:

1. Stop accepting new control requests.
2. Persist the final in-memory state.
3. Close API and DROP sessions.
4. Stop background threads.
5. Exit cleanly.

Recommended initial value:

```yaml
terminationGracePeriodSeconds: 30
```

The application must handle `SIGTERM`.

---

# 15. Completed Backend Work

## 15.1 Transport Layer

Completed:

* TCP socket abstraction
* Connection handling
* Socket timeout support
* Socket close handling
* Detection of remote connection closure

## 15.2 SoupBinTCP Layer

Completed:

* SoupBinTCP login
* Login accepted handling
* Login rejection handling
* Heartbeat handling
* Sequenced packet handling
* End-of-session handling
* Logout handling
* Requested Soup sequence support

## 15.3 API Protocol

Completed:

* JSON specification-driven API message definitions
* Little-endian binary encoding
* Mercury API message header handling
* User state request
* Firm state request
* Market state request
* Correlation ID generation and return

Supported API operations:

```python
api_client.update_user_state(
    user_id,
    state,
)

api_client.update_firm_state(
    firm_id,
    state,
)

api_client.update_market_state(
    market_id,
    state,
)
```

## 15.4 DROP Protocol

Completed:

* Generic JSON-driven DROP decoder
* SBE header decoding
* Mercury header decoding
* Matching-engine sequence extraction
* Dynamic timestamp handling
* Unsupported-template detection
* Unsupported-template logging only once

Supported DROP templates currently include:

* User definition
* User status
* Firm definition
* Firm status
* Market definition
* Market trading state

## 15.5 Application State

Completed:

* Thread-safe `UserStateStore`
* Thread-safe `FirmStateStore`
* Thread-safe `MarketStateStore`
* Combined `ApplicationState`
* State snapshots
* Entity counts
* Record lookup
* Condition-variable notifications
* Waiting for entity creation
* Waiting for a newer requested state

Available state structure:

```python
application_state.users
application_state.firms
application_state.markets
```

## 15.6 DROP State Service

Completed:

* Background worker thread
* Continuous DROP receiving
* Initial replay processing
* Application state reconstruction
* Supported-message counters
* Applied-message counters
* Unsupported-template reporting
* Manual stop
* Service status
* Disconnect reason tracking
* Exact next Soup sequence tracking

## 15.7 Automatic Reconnection

Completed:

* Reconnect after TCP connection closure
* Resume from exact next Soup sequence
* Preserve ApplicationState during reconnect
* Advance sequence for supported messages
* Advance sequence for unsupported messages
* Configurable reconnect delay
* Configurable reconnect limit
* Unlimited production reconnect mode

Validated behavior:

```text
Initial connection requested sequence 1
    ↓
Replay consumed
    ↓
Connection closed
    ↓
Reconnect requested next sequence
    ↓
Live updates received
```

## 15.8 Control Confirmation

Completed:

* `ControlService`
* User state control
* Firm state control
* Market state control
* API correlation ID return
* DROP confirmation waiting
* Newer-sequence validation
* Confirmation timeout
* Typed `ControlResult`

Example:

```python
result = control_service.update_user_state(
    402,
    "S",
)
```

A successful result means:

```text
API request sent
+
correlation ID generated
+
new DROP state received
+
ApplicationState updated
```

## 15.9 Integration Testing

Completed test coverage:

* DROP message decoding
* DROP state reconstruction
* User API state updates
* Firm API state updates
* Market API state updates
* DROP automatic reconnection
* Control request confirmation
* Automatic restoration of the original test state

Confirmed user test:

```text
User 402:
A → S confirmed through DROP
S → A confirmed through DROP
```

---

# 16. Currently Unsupported DROP Templates

The decoder currently reports these unsupported template IDs:

```text
2, 5, 6, 7, 8, 9,
23, 24, 25,
28, 29, 32,
42, 44, 45,
53, 54, 55
```

Before production, each template must be classified.

For every unsupported template:

```text
Does it affect users, firms, markets, sessions, or control confirmation?
    │
    ├── Yes
    │      → implement decoding and state handling
    │
    └── No
           → document as intentionally ignored
```

This classification is important before persisting checkpoints.

The application must not save a checkpoint after ignoring a message that should have updated required operational state.

---

# 17. Remaining Backend Work

## Priority 1 — Protocol Reliability

* Classify all unsupported DROP templates
* Implement relevant templates
* Document safely ignored templates
* Add duplicate and stale sequence protection to state stores
* Verify accepted Soup session identifier handling
* Verify end-of-session behavior
* Add API client connection recovery
* Add API heartbeat and session health monitoring
* Confirm behavior when the API server closes the socket
* Confirm behavior when the requested DROP sequence is unavailable
* Implement safe full-replay fallback

## Priority 2 — Snapshot Models

Create:

```text
backend/persistence/
├── __init__.py
├── snapshot.py
└── file_snapshot_repository.py
```

Required responsibilities:

### `snapshot.py`

* Snapshot schema definition
* Snapshot version
* Snapshot validation
* User serialization
* Firm serialization
* Market serialization
* Application state restoration
* Business-date validation
* Soup-session validation

### `file_snapshot_repository.py`

* Load snapshot
* Save snapshot atomically
* Check whether a snapshot exists
* Delete current snapshot
* Mark invalid snapshot
* Ensure persistence directory exists
* Synchronize file and directory writes

## Priority 3 — Persistence Service

Create:

```text
backend/services/snapshot_persistence_service.py
```

Responsibilities:

* Run periodic persistence worker
* Track dirty state
* Track sequence changes
* Save every configured interval
* Save immediately after control confirmation
* Save during graceful shutdown
* Save final completed snapshot
* Expose persistence health
* Report last successful save time
* Report last persistence error

## Priority 4 — State Restoration

Add support for:

```text
Load snapshot
    ↓
Validate current session
    ↓
Restore ApplicationState
    ↓
Set starting Soup sequence
    ↓
Start DropStateService
```

ApplicationState requires restoration methods such as:

```python
application_state.restore(
    snapshot,
)
```

or store-level methods such as:

```python
application_state.users.restore(...)
application_state.firms.restore(...)
application_state.markets.restore(...)
```

## Priority 5 — DropStateService Integration

Integrate persistence into `DropStateService`.

The service should:

* Use the restored starting sequence
* Keep state during network reconnect
* Mark persistence dirty after sequenced packets
* Notify persistence of checkpoint changes
* Save final state on end-of-session
* Stop reconnecting after Soup `Z`
* Use full replay when the restored checkpoint is invalid

Persistence logic should be provided through an interface rather than hardcoded throughout the DROP protocol layer.

## Priority 6 — Production Application Bootstrap

Create:

```text
backend/application.py
backend/main.py
```

The application bootstrap owns one shared instance of:

```text
DropClient
ApiClient
ApplicationState
DropStateService
ControlService
FileSnapshotRepository
SnapshotPersistenceService
```

Startup order:

```text
Load configuration
    ↓
Load and validate snapshot
    ↓
Restore ApplicationState when valid
    ↓
Create DropClient
    ↓
Create DropStateService
    ↓
Start persistence service
    ↓
Start DROP state service
    ↓
Connect ApiClient
    ↓
Create ControlService
    ↓
Start REST server
```

Shutdown order:

```text
Stop accepting control requests
    ↓
Save immediate snapshot
    ↓
Stop DropStateService
    ↓
Close ApiClient
    ↓
Stop persistence service
    ↓
Exit
```

## Priority 7 — REST API

Suggested endpoints:

```text
GET  /api/v1/status

GET  /api/v1/users
GET  /api/v1/users/{user_id}
POST /api/v1/users/{user_id}/state

GET  /api/v1/firms
GET  /api/v1/firms/{firm_id}
POST /api/v1/firms/{firm_id}/state

GET  /api/v1/markets
GET  /api/v1/markets/{market_id}
POST /api/v1/markets/{market_id}/state

GET  /health/live
GET  /health/ready
GET  /metrics
```

Example request:

```json
{
  "state": "S"
}
```

Example confirmed response:

```json
{
  "entity_type": "user",
  "entity_id": 402,
  "requested_state": "S",
  "correlation_id": 1785398733349910,
  "confirmed_sequence": 8884,
  "status": "CONFIRMED"
}
```

## Priority 8 — Live Frontend Updates

Use one of:

```text
Server-Sent Events
or
WebSocket
```

Possible event types:

```text
user_state_changed
firm_state_changed
market_state_changed
drop_connected
drop_disconnected
drop_reconnected
session_completed
control_confirmed
control_failed
```

## Priority 9 — Authentication and Authorization

The backend should integrate with Keycloak.

Required security behavior:

* Validate JWT signature
* Validate token issuer
* Validate token audience
* Validate token expiry
* Require authenticated users
* Define viewer and operator roles
* Allow read access to viewers
* Allow control actions only to operators
* Obtain username from the validated token
* Never trust a username provided in the request body
* Keep DROP and API passwords in Kubernetes Secrets
* Never log protocol passwords

Suggested roles:

```text
market-control-viewer
market-control-operator
market-control-admin
```

## Priority 10 — Kubernetes Deployment

Required resources:

```text
Deployment
Service
Ingress
PersistentVolumeClaim
ConfigMap
Secret
NetworkPolicy
PodDisruptionBudget
ServiceAccount
```

Deployment requirements:

* One replica
* PVC mounted at `/data/market-control`
* Credentials from Secret
* Non-secret settings from ConfigMap
* Resource requests
* Resource limits
* Readiness probe
* Liveness probe
* Graceful shutdown
* Restricted security context
* Structured logs
* Controlled rolling-update strategy

---

# 18. Health Checks

## Liveness

The process is alive and internal worker threads have not crashed.

Example:

```text
GET /health/live
```

Possible response:

```json
{
  "status": "UP"
}
```

## Readiness

The pod is ready only when:

* Snapshot restoration completed or fresh replay started
* ApplicationState is available
* DROP service is running or reconnecting normally
* API client is available for control requests
* Persistence directory is writable
* No fatal session error exists

Example:

```text
GET /health/ready
```

Possible response:

```json
{
  "status": "READY",
  "drop_connected": true,
  "api_connected": true,
  "state_initialized": true,
  "snapshot_writable": true
}
```

During initial replay, read-only endpoints may be available while control endpoints remain unavailable.

---

# 19. Observability

Recommended metrics:

```text
drop_connected
drop_reconnect_total
drop_received_packets_total
drop_supported_messages_total
drop_unsupported_messages_total
drop_last_message_timestamp
drop_next_soup_sequence

application_users
application_firms
application_markets

control_requests_total
control_confirmations_total
control_timeouts_total
control_failures_total
control_confirmation_seconds

snapshot_save_total
snapshot_save_failures_total
snapshot_last_success_timestamp
snapshot_age_seconds
snapshot_next_soup_sequence
```

Recommended structured log events:

```text
drop_connected
drop_connection_closed
drop_reconnect_started
drop_reconnect_succeeded
drop_end_of_session
snapshot_loaded
snapshot_saved
snapshot_invalid
full_replay_started
full_replay_completed
control_sent
control_confirmed
control_timed_out
```

Credentials and binary payloads must not be written to production logs.

---

# 20. Failure Scenarios to Test

## DROP failures

* TCP disconnect during initial replay
* TCP disconnect during live operation
* Multiple repeated reconnects
* Unsupported DROP template
* Malformed DROP packet
* Duplicate DROP packet
* Stale matching-engine sequence
* Soup End-of-Session
* Invalid requested Soup sequence
* Requested sequence no longer available
* DROP login rejected

## API failures

* API TCP disconnect
* API login rejected
* API request write failure
* API heartbeat timeout
* Control request rejected
* No DROP confirmation
* Delayed DROP confirmation
* Duplicate control submission
* API reconnect during a control request

## Persistence failures

* Missing snapshot
* Empty snapshot
* Invalid JSON
* Unsupported snapshot version
* Stale business date
* Different Soup session
* Partial temporary file
* PVC temporarily unwritable
* Pod crash during snapshot write
* Pod restart after a valid snapshot
* Snapshot checkpoint older than memory
* Corrupted state record
* Disk full

## Kubernetes failures

* Pod deletion during live operation
* Node drain
* Rolling deployment
* SIGTERM during control confirmation
* PVC remount after pod restart
* Application restart during initial replay
* Liveness failure
* Readiness failure

---

# 21. Recommended Implementation Order

## Phase 1 — Protocol Hardening

* [ ] Classify unsupported DROP templates
* [ ] Implement relevant DROP templates
* [ ] Document intentionally ignored templates
* [ ] Add stale and duplicate update protection
* [ ] Verify Soup session identifier behavior
* [ ] Add API connection recovery
* [ ] Add full-replay fallback

## Phase 2 — Snapshot Model

* [ ] Create `backend/persistence/__init__.py`
* [ ] Create `backend/persistence/snapshot.py`
* [ ] Define snapshot schema version
* [ ] Implement state serialization
* [ ] Implement snapshot validation
* [ ] Implement state restoration

## Phase 3 — File Repository

* [ ] Create `backend/persistence/file_snapshot_repository.py`
* [ ] Implement snapshot loading
* [ ] Implement atomic snapshot saving
* [ ] Implement temporary-file handling
* [ ] Implement invalid snapshot quarantine
* [ ] Implement snapshot deletion
* [ ] Add repository unit tests

## Phase 4 — Persistence Worker

* [ ] Create `SnapshotPersistenceService`
* [ ] Add dirty-state tracking
* [ ] Add periodic save interval
* [ ] Add immediate save method
* [ ] Add graceful shutdown save
* [ ] Add persistence status and errors
* [ ] Add persistence worker tests

## Phase 5 — Startup Recovery

* [ ] Load snapshot during application startup
* [ ] Validate business date
* [ ] Validate Soup session
* [ ] Restore ApplicationState
* [ ] Resume from saved Soup sequence
* [ ] Fall back to sequence 1 when invalid
* [ ] Add pod-restart integration test

## Phase 6 — Session Lifecycle

* [ ] Detect Soup End-of-Session
* [ ] Save final snapshot
* [ ] Mark snapshot completed
* [ ] Stop reconnecting
* [ ] Detect a new session
* [ ] Replace previous snapshot
* [ ] Clear state for a new session
* [ ] Rebuild from sequence 1

## Phase 7 — Application Bootstrap

* [ ] Create `backend/application.py`
* [ ] Create `backend/main.py`
* [ ] Add startup sequencing
* [ ] Add SIGTERM handling
* [ ] Add shutdown sequencing
* [ ] Move test-only object construction into the application

## Phase 8 — REST API

* [ ] Add status endpoint
* [ ] Add user endpoints
* [ ] Add firm endpoints
* [ ] Add market endpoints
* [ ] Add control endpoints
* [ ] Add error mapping
* [ ] Add request validation
* [ ] Add REST integration tests

## Phase 9 — Security

* [ ] Add Keycloak JWT validation
* [ ] Add viewer role
* [ ] Add operator role
* [ ] Add admin role if needed
* [ ] Secure credentials with Kubernetes Secrets
* [ ] Add NetworkPolicy
* [ ] Review production logs

## Phase 10 — Kubernetes

* [ ] Add PVC template
* [ ] Add volume mount
* [ ] Set replica count to one
* [ ] Add readiness probe
* [ ] Add liveness probe
* [ ] Add graceful shutdown period
* [ ] Add resources
* [ ] Add security context
* [ ] Add PodDisruptionBudget
* [ ] Add deployment tests

---

# 22. Proposed Project Structure

```text
market_ctrl/
├── backend/
│   ├── application.py
│   ├── main.py
│   ├── settings.py
│   │
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── snapshot.py
│   │   └── file_snapshot_repository.py
│   │
│   ├── protocol/
│   │   ├── errors.py
│   │   │
│   │   ├── api/
│   │   │   ├── client.py
│   │   │   ├── message_format.py
│   │   │   └── messages.py
│   │   │
│   │   ├── drop/
│   │   │   ├── client.py
│   │   │   ├── message_format.py
│   │   │   └── messages.py
│   │   │
│   │   ├── soup/
│   │   │   ├── message_format.py
│   │   │   ├── messages.py
│   │   │   └── session.py
│   │   │
│   │   └── transport/
│   │       └── socket.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── control_service.py
│   │   ├── drop_state_service.py
│   │   └── snapshot_persistence_service.py
│   │
│   ├── state/
│   │   ├── application_state.py
│   │   ├── firm_state.py
│   │   ├── market_state.py
│   │   └── user_state.py
│   │
│   └── specs/
│       ├── soup_api_spec.json
│       └── soup_drop_spec.json
│
├── helm/
│   ├── templates/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── configmap.yaml
│   │   ├── secret.yaml
│   │   ├── persistentvolumeclaim.yaml
│   │   ├── networkpolicy.yaml
│   │   └── pdb.yaml
│   └── values.yaml
│
├── test_drop_message.py
├── test_drop_state_service.py
├── test_api_user_state.py
├── test_api_firm_state.py
├── test_api_market_state.py
├── test_control_service.py
└── MARKET_CONTROL_BACKEND_PLAN.md
```

---

# 23. Initial Production Configuration

Example environment variables:

```text
DROP_HOST
DROP_PORT
DROP_USERNAME
DROP_PASSWORD
DROP_SESSION
DROP_START_SEQUENCE

API_HOST
API_PORT
API_USERNAME
API_PASSWORD

SNAPSHOT_PATH
SNAPSHOT_INTERVAL_SECONDS
CONFIRMATION_TIMEOUT_SECONDS
RECONNECT_DELAY_SECONDS

KEYCLOAK_ISSUER
KEYCLOAK_AUDIENCE
```

Recommended initial values:

```text
SNAPSHOT_PATH=/data/market-control/current_session.json
SNAPSHOT_INTERVAL_SECONDS=5
CONFIRMATION_TIMEOUT_SECONDS=10
RECONNECT_DELAY_SECONDS=1
```

Production reconnect attempts should be unlimited unless the application encounters a fatal protocol or authentication error.

---

# 24. Current Project Status Summary

## Working

```text
TCP transport
SoupBinTCP sessions
API user control
API firm control
API market control
DROP decoding
User state reconstruction
Firm state reconstruction
Market state reconstruction
Continuous background DROP processing
Soup sequence tracking
TCP reconnection
Application state preservation during reconnect
Control confirmation through DROP
User suspend and restore integration test
Environment-based credentials
```

## Not Yet Implemented

```text
Persistent snapshot
Pod restart recovery
Business-date validation
Soup-session validation
New-session reset
Snapshot corruption recovery
Duplicate replay protection review
API reconnection
REST API
Keycloak authorization
Frontend live event delivery
Production application bootstrap
Kubernetes PVC
Kubernetes probes
Metrics
Production logging policy
```

---

# 25. Final Approved Persistence Decision

```text
PostgreSQL:
    Not used

Redis:
    Not used

Persistent storage:
    Kubernetes ReadWriteOnce PVC

Persistence format:
    One atomic JSON snapshot

Snapshot retention:
    Current business session only

Previous business-day data:
    Deleted or overwritten when the next session starts

Full DROP history:
    Not stored

Market data history:
    Not stored

Backend replicas:
    One active replica

Recovery behavior:
    Restore current state and resume from saved next Soup sequence

Fallback behavior:
    Clear state and replay from sequence 1
```

---

# 26. Definition of Production-Ready

The backend can be considered production-ready when:

* All required DROP templates are handled or explicitly documented as ignored.
* State stores safely handle duplicate replay.
* TCP disconnects reconnect without losing state.
* Pod restarts restore state from the PVC.
* Pod restarts resume from the saved Soup sequence.
* Invalid snapshots safely fall back to a full replay.
* New sessions never restore previous-session state.
* End-of-session state is finalized correctly.
* API controls are confirmed through DROP.
* API connection failures recover safely.
* REST endpoints are authenticated through Keycloak.
* Only authorized operators can send controls.
* Kubernetes health checks reflect real service health.
* Graceful shutdown saves a final snapshot.
* PVC failures are visible through logs, health status, and metrics.
* Failure and recovery scenarios have been tested.
