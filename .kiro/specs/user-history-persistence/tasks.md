# Implementation Plan: User History Persistence

## Overview

Implement a file-based persistence layer for per-user conversation history summaries. The `UserHistoryService` class will handle saving, loading, deleting, and injecting user history into conversation context. Integration hooks into `PDNAgent._summarize_old_turns()` (save) and `chat_routes.py` (load on conversation start).

## Tasks

- [x] 1. Create UserHistoryService with core data types and validation
  - [x] 1.1 Create `app/utils/user_history_service.py` with `UserHistoryPayload` dataclass, constants (`SCHEMA_VERSION`, `HISTORY_FILENAME_SUFFIX`), and `UserHistoryService` class skeleton
    - Define `UserHistoryPayload` with `to_dict()` and `from_dict()` class methods
    - Define `SCHEMA_VERSION = "1.0"` and `HISTORY_FILENAME_SUFFIX = "_history.enc"`
    - Initialize `UserHistoryService.__init__(self, base_dir=None)` using `SAVED_RESULTS_DIR` env var or `"saved_results"` default
    - _References design: Core Interfaces/Types, Function 7, Function 8_

  - [x] 1.2 Implement `validate_user_id()` method
    - Reject empty/whitespace-only strings
    - Reject path traversal sequences (`..`, `/`, `\`, null bytes)
    - Use regex pattern `^[a-zA-Z0-9._@+\-]+$` for allowed characters
    - Return `bool` with no side effects
    - _References design: Function 8, Property 5, Property 13_

  - [x] 1.3 Implement `_build_history_filename()` method
    - Strip last domain suffix from email (e.g., `tomergur@gmail.com` → `tomergur@gmail_history.enc`)
    - Handle non-email user_ids by using the raw string
    - _References design: Function 7, Property 9_

  - [x] 1.4 Implement `resolve_user_history_path()` method
    - Use `PDNFilePath.get_user_dir()` for folder resolution (reuse existing convention)
    - Combine user dir with `_build_history_filename()` result
    - Add safety check: resolved path must be under `self.base_dir`
    - Create parent directory if it does not exist
    - _References design: Function 7, Property 14_

  - [x] 1.5 Write property tests for validation and path resolution
    - **Property 5: Path traversal prevention** — malicious user_ids are rejected
    - **Property 9: Filename generation** — strips last domain suffix correctly
    - **Property 13: validate_user_id accepts + character** — special chars in emails
    - **Property 14: resolve_user_history_path creates directory** — parent dir exists after resolve
    - **Validates: Design Properties 5, 9, 13, 14**

- [x] 2. Implement encryption and save/load/delete operations
  - [x] 2.1 Implement `encrypt_payload()` and `decrypt_payload()` methods
    - `encrypt_payload`: base64 encode UTF-8 JSON string to bytes
    - `decrypt_payload`: base64 decode bytes back to UTF-8 string, return `None` on failure
    - Never raise exceptions from `decrypt_payload`
    - _References design: Function 5, Function 6, Property 2, Property 3_

  - [x] 2.2 Implement `save_user_history()` with atomic write and file locking
    - Validate user_id and reject empty summaries
    - Build `UserHistoryPayload` with current UTC timestamp
    - Serialize to JSON, encrypt, then write atomically (temp file + `os.replace`)
    - Use `fcntl.flock(LOCK_EX)` for concurrency safety
    - Clean up temp files on failure, clean up lock file on success
    - Return `bool` indicating success
    - _References design: Function 1, Save Algorithm, Property 4, Property 8_

  - [x] 2.3 Implement `load_user_history()` with graceful degradation
    - Validate user_id, check file existence
    - Read bytes, decrypt, parse JSON, construct `UserHistoryPayload`
    - Return `None` on any failure (missing file, corruption, decode error)
    - Never raise exceptions to caller
    - _References design: Function 2, Load Algorithm, Property 1_

  - [x] 2.4 Implement `delete_user_history()`
    - Validate user_id, resolve path, unlink file with `missing_ok=True`
    - Also remove `.lock` file if present
    - Return `True` on success or if file was already absent
    - Return `False` only on unexpected OS errors
    - _References design: Function 3, Delete Algorithm, Property 6_

  - [x] 2.5 Write property tests for encryption and persistence round-trip
    - **Property 1: Round-trip integrity** — save then load returns same data
    - **Property 2: Encryption round-trip** — encrypt then decrypt is identity
    - **Property 3: Encryption obfuscation** — encrypted output is never valid JSON
    - **Property 4: Atomic write safety** — file always contains complete valid payload
    - **Property 6: Delete idempotency** — deleting non-existent history returns True
    - **Property 8: Override semantics** — each save fully replaces previous content
    - **Property 12: Unicode/Hebrew summary round-trip** — Hebrew text survives persistence
    - **Validates: Design Properties 1, 2, 3, 4, 6, 8, 12**

- [x] 3. Implement context injection
  - [x] 3.1 Implement `inject_user_history_into_context()` method
    - Return messages unchanged if payload is `None` or summary is empty
    - Build history system message with `[Previous Session Summary]` header/footer
    - Insert after the first system message (or at index 0 if no system message exists)
    - Preserve all original messages in order
    - _References design: Function 4, Property 7, Property 10, Property 11_

  - [x] 3.2 Write property tests for context injection
    - **Property 7: Context injection preserves original messages** — no messages removed or modified
    - **Property 10: Context injection with empty messages** — handles edge cases
    - **Property 11: Context injection with multiple system messages** — inserts after FIRST system message only
    - **Validates: Design Properties 7, 10, 11**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Integrate with PDNAgent and chat routes
  - [x] 5.1 Hook save into `PDNAgent._summarize_old_turns()`
    - Import `UserHistoryService` in `pdn_agent.py`
    - Initialize `self.history_service` in `PDNAgent.__init__()` using the same base dir as token usage
    - After successful summarization in `_summarize_old_turns()`, call `self.history_service.save_user_history(user_name, new_summary, metadata)`
    - Only save if summary is non-empty; skip silently otherwise
    - _References design: Integration Points, Save trigger_

  - [x] 5.2 Hook load into `chat_routes.py` conversation start
    - Import `UserHistoryService` in `chat_routes.py`
    - In the login success flow or chat interface initialization, load user history via `service.load_user_history(user_email)`
    - Store loaded payload in session or pass to agent for context injection
    - _References design: Integration Points, Load trigger_

  - [x] 5.3 Wire context injection into chat flow
    - Before calling `agent.chat_with_binat()`, inject loaded history into the conversation context
    - Use `inject_user_history_into_context()` to prepend history summary to messages
    - Ensure history is loaded only once per session start (not on every message)
    - _References design: Integration Points, Context Injection_

  - [x] 5.4 Write integration tests for save/load lifecycle
    - Test full flow: login → chat → summarize → save → new session → load → inject
    - Test that history survives agent restart
    - _References design: Example Usage_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The design uses Python with `fcntl` file locking (Linux/macOS only)
- Encryption is MVP base64 obfuscation — can be upgraded later without changing the interface
- Property tests validate the 14 correctness properties defined in the design document
- Reuses existing `PDNFilePath` utility for folder resolution consistency
