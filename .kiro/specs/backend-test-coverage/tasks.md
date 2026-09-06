# Implementation Plan: Backend Test Coverage

## Overview

Incrementally build test coverage to ≥90% across four backend modules (`pdn_admin`, `pdn_chat_ai`, `pdn_relationships`, `pdn_diagnose`). Tasks are ordered from simpler modules (constants, logger) to more complex ones (agents, routes), extending existing test files with fully mocked external dependencies.

## Tasks

- [x] 1. Relationship Constants and Logger (Simple Modules)
  - [x] 1.1 Add tests for constants.py in tests/test_relationship_routes.py
    - Verify RelationshipType enum contains exactly "partner", "friend", "colleague"
    - Verify PDN_CODES list contains exactly 12 codes matching expected pattern
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 1.2 Add tests for logger.py in tests/test_chat_routes.py
    - Test setup_logger returns logger with correct name, level, and handler
    - Test idempotent behavior: multiple calls with same name produce no duplicate handlers
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 1.3 Write property test for logger idempotence in tests/test_chat_improvements.py
    - **Property 9: Logger Setup Idempotence**
    - For any logger name and N repeated calls, verify exactly one handler exists
    - **Validates: Requirements 5.3**

- [x] 2. Coupon Manager Coverage
  - [x] 2.1 Add coupon CRUD tests in tests/test_coupon_admin_routes.py
    - Test create_coupon with auto-generated and custom codes, duplicate rejection
    - Test validate_coupon for valid, exhausted, and non-existent codes
    - Test validate_and_redeem for atomic validation+redemption and email deduplication
    - Test update_coupon for allowed fields and immutable code field rejection
    - Test delete_coupon for success and KeyError on non-existent codes
    - Mock JSON file I/O for _save_to_file and _load_initial_data
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 2.2 Write property test for coupon code generation in tests/test_coupon_properties.py
    - **Property 4: Coupon Code Generation Uniqueness and Charset**
    - For any set of existing codes, generated code is unique, uppercase+digits, 8 chars
    - **Validates: Requirements 3.2, 3.8**

  - [x] 2.3 Write property test for coupon validation state in tests/test_coupon_properties.py
    - **Property 5: Coupon Validation Reflects Usage State**
    - Valid iff usage_count < max_usage; invalid for non-existent codes
    - **Validates: Requirements 3.3**

  - [x] 2.4 Write property test for validate-and-redeem atomicity in tests/test_coupon_properties.py
    - **Property 6: Coupon Validate-and-Redeem Atomicity with Email Deduplication**
    - Atomically increments usage_count by 1; email appears in used_by at most once
    - **Validates: Requirements 3.4**

  - [x] 2.5 Write property test for coupon code immutability in tests/test_coupon_properties.py
    - **Property 7: Coupon Code Immutability on Update**
    - Any update including "code" field raises ValueError
    - **Validates: Requirements 3.5**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. User Manager Coverage
  - [x] 4.1 Add user CRUD and validation tests in tests/test_user_manager_coverage.py
    - Test add_user: success, duplicate email, invalid email, invalid PDN code
    - Test verify_password: correct, incorrect, non-existent user (timing-safe)
    - Test update_user: allowed fields, password re-hashing, pdn_code/limit/name/gender validation
    - Test delete_user: success and KeyError for non-existent
    - Test _migrate_plaintext_passwords: converts plaintext to bcrypt
    - Test get_available_pdn_codes: mock PROMPTS_DIR for .prompt file discovery
    - Mock JSON file I/O for _save_to_file and _load_users
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

  - [x] 4.2 Write property test for user creation validation in tests/test_user_manager_coverage.py
    - **Property 10: User Creation Validation Rules**
    - Invalid email format → ValueError; invalid pdn_code → ValueError; duplicate email → ValueError
    - **Validates: Requirements 6.2**

  - [x] 4.3 Write property test for password hash round-trip in tests/test_user_manager_coverage.py
    - **Property 11: Password Hash Round-Trip**
    - verify_password(email, P) → True; verify_password(email, Q≠P) → False
    - **Validates: Requirements 6.3**

  - [x] 4.4 Write property test for user update validation in tests/test_user_manager_coverage.py
    - **Property 12: User Update Validation Rules**
    - Invalid pdn_code, non-positive limit, empty name, invalid gender → ValueError
    - **Validates: Requirements 6.4**

  - [x] 4.5 Write property test for plaintext password migration in tests/test_user_manager_coverage.py
    - **Property 13: Plaintext Password Migration**
    - After migration, stored password starts with $2b$ and original verifies correctly
    - **Validates: Requirements 6.6**

- [x] 5. Admin Routes Coverage
  - [x] 5.1 Add session management tests in tests/test_admin_routes_coverage.py
    - Test admin login with correct/incorrect password (mock ADMIN_PASSWORD config)
    - Test create_session, verify_session, cleanup_expired_sessions, require_admin_session decorator
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 5.2 Write property test for session lifecycle in tests/test_admin_routes_coverage.py
    - **Property 1: Session Lifecycle Validity**
    - Created session verifies; expired session rejects
    - **Validates: Requirements 1.3**

  - [x] 5.3 Add user metadata and email tests in tests/test_admin_routes_coverage.py
    - Test load_user_metadata, get_user_questionnaire, get_user_voice with mocked UserMetadataHandler and CSV
    - Test send_user_email and send_binat_invite with mocked email functions
    - Test recalculate_user_pdn with mocked load_answers and calculate_pdn_code
    - Test invalid input returns HTTP 400/404
    - _Requirements: 1.4, 1.5, 1.6, 1.8_

  - [x] 5.4 Add audio routes tests in tests/test_admin_routes_coverage.py
    - Test full file request returns 200 with audio/wav content (mock file system)
    - Test range request returns 206 with correct Content-Range headers
    - Test non-existent file returns 404
    - Test invalid range returns 416
    - Test empty file returns 404
    - Test path traversal protection returns 403
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 1.7_

  - [x] 5.5 Write property test for path traversal protection in tests/test_admin_routes_coverage.py
    - **Property 2: Path Traversal Protection**
    - Any path resolving outside SAVED_RESULTS_DIR → HTTP 403
    - **Validates: Requirements 1.7**

  - [x] 5.6 Write property test for audio range requests in tests/test_admin_routes_coverage.py
    - **Property 3: Audio Range Request Correctness**
    - Valid range (start, end) → 206 with correct Content-Range and body length
    - **Validates: Requirements 2.3**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. PDN Agent Coverage
  - [x] 7.1 Add chat and prompt tests in tests/test_pdn_agent.py
    - Test chat_with_binat: mock _invoke_llm, verify prompt composition, history formatting, input sanitization
    - Test build_21_transformation_plan: mock _invoke_llm, verify goal-based prompt and response
    - Test daily_training: mock _invoke_llm, verify task-based prompt and response
    - Test _load_prompt: mock file reads, verify caching, guardrails inclusion, ValueError for invalid codes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 7.2 Add usage stats and response cleaning tests in tests/test_pdn_agent_refactored.py
    - Test get_usage_stats: provide synthetic token_usage, verify cost calculations, projections, recommendations
    - Test _clean_response: verify removal of internal prompt markers
    - Test daily limit enforcement: exceeded limit returns message without LLM call
    - _Requirements: 7.6, 7.7, 7.8_

  - [x] 7.3 Write property test for usage stats cost calculation in tests/test_pdn_agent_refactored.py
    - **Property 15: Usage Stats Cost Calculation Invariant**
    - Cost = (uncached_input/1e6 × input_price) + (output/1e6 × output_price) + (cache_creation/1e6 × cache_write_price) + (cache_read/1e6 × cache_read_price)
    - **Validates: Requirements 7.6**

  - [x] 7.4 Write property test for response marker cleaning in tests/test_pdn_agent_refactored.py
    - **Property 16: Response Marker Cleaning**
    - Any string with [STOP...] markers → cleaned output has no such markers
    - **Validates: Requirements 7.7**

  - [x] 7.5 Write property test for prompt loading caching in tests/test_pdn_agent.py
    - **Property 14: Prompt Loading Caching and Validation**
    - Two calls with same args → identical result, file read only on first call; invalid code → ValueError
    - **Validates: Requirements 7.5**

- [x] 8. Base PDN Agent Coverage
  - [x] 8.1 Add LLM initialization and history tests in tests/test_pdn_agent_history.py
    - Test _initialize_llm: mock API keys, verify Anthropic and OpenAI provider paths
    - Test _add_to_history: verify turn accumulation, summarization trigger by turn limit and token limit
    - Test _summarize_old_turns: mock summary_llm, verify summary generation, history truncation, persistence
    - Test summarization failure: verify graceful fallback with history truncation
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.10_

  - [x] 8.2 Add daily limits, token tracking, and persistence tests in tests/test_pdn_agent_history.py
    - Test _has_exceeded_daily_limit: verify limit enforcement, daily reset, exempt user bypass
    - Test _track_usage: verify per-user per-day token accumulation and file persistence debouncing
    - Test persist_session: mock summary_llm, verify forced summarization and disk persistence
    - Test _sanitize_user_input: verify prompt injection patterns are neutralized
    - Test _build_system_message: verify Anthropic cache_control and OpenAI plain SystemMessage
    - _Requirements: 8.5, 8.6, 8.7, 8.8, 8.9_

  - [x] 8.3 Write property test for daily limit enforcement in tests/test_property_base_agent.py
    - **Property 17: Daily Conversation Limit Enforcement**
    - Non-exempt user at/above limit → True; exempt user → always False
    - **Validates: Requirements 8.5**

  - [x] 8.4 Write property test for conversation history summarization in tests/test_property_base_agent.py
    - **Property 18: Conversation History Summarization Lifecycle**
    - When turn count or token count exceeds threshold → raw ≤ RAW_TURNS_TO_KEEP, summary non-empty
    - **Validates: Requirements 8.3, 8.4**

  - [x] 8.5 Write property test for token usage accumulation in tests/test_property_base_agent.py
    - **Property 19: Token Usage Accumulation Invariant**
    - N tracked responses → stored tokens = sum of individual tokens, calls = N
    - **Validates: Requirements 8.6**

  - [x] 8.6 Write property test for input sanitization in tests/test_property_base_agent.py
    - **Property 20: Input Sanitization Neutralizes Injection Patterns**
    - XML-like tags → angle brackets replaced with full-width equivalents
    - **Validates: Requirements 8.8**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Relationship Agent and Routes Coverage
  - [x] 10.1 Add relationship agent tests in tests/test_relationship_agent.py
    - Test chat: mock _invoke_llm, verify prompt includes user+partner PDN codes, relationship type, history
    - Test _load_relationship_prompt: mock file reads, verify composition order and caching
    - Test _load_code_data: verify success and ValueError for empty/unknown codes
    - Test daily limit enforcement returns DAILY_LIMIT_MESSAGE without LLM call
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 10.2 Add relationship routes tests in tests/test_relationship_routes.py
    - Test login: mock get_user_manager, verify valid partner_code+relationship_type, rejection of invalid
    - Test chat: mock get_relationship_agent, verify message validation, stats tracking, history, response
    - Test logout: verify agent.persist_session called and session cleared
    - Test handle_errors decorator: ValueError→400, TimeoutError→503, Exception→500
    - Test message exceeding 5000 chars returns HTTP 400
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 10.3 Write property test for error-to-status mapping in tests/test_property_relationship_routes.py
    - **Property 8: Error Decorator Exception-to-Status Mapping**
    - ValueError→400, TimeoutError→503, Exception→500
    - **Validates: Requirements 10.5**

  - [x] 10.4 Write property test for relationship prompt caching in tests/test_property_relationship_agent.py
    - **Property 14: Prompt Loading Caching and Validation (relationship variant)**
    - Two calls same args → identical result, file read only first call; invalid code → ValueError
    - **Validates: Requirements 9.3, 9.4**

- [x] 11. Chat Routes and Diagnosis Routes Coverage
  - [x] 11.1 Add chat routes tests in tests/test_chat_routes.py
    - Test login: mock get_user_manager, verify success, failure, missing fields
    - Test chat: mock PDNAgent.chat_with_binat, verify message validation, stats tracking, response
    - Test 21-day plan: mock PDNAgent.build_21_transformation_plan, verify goal validation and response
    - Test daily training: mock PDNAgent.daily_training, verify task validation and response
    - Test logout: verify persist_session and session clearing
    - Test message exceeding 5000 chars returns HTTP 400
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8_

  - [x] 11.2 Add chat error handling tests in tests/test_chat_improvements.py
    - Test handle_errors decorator: ValidationError→400, AuthenticationError→401, RateLimitExceeded→429, TimeoutError→503, Exception→500
    - _Requirements: 4.7_

  - [x] 11.3 Write property test for chat error-to-status mapping in tests/test_chat_improvements.py
    - **Property 8: Error Decorator Exception-to-Status Mapping (chat variant)**
    - ValidationError→400, AuthenticationError→401, RateLimitExceeded→429, TimeoutError→503, Exception→500
    - **Validates: Requirements 4.7**

  - [x] 11.4 Add diagnosis routes tests in tests/test_diagnosis_routes_coverage.py
    - Test login: email/password and coupon-based auth, invalid credentials, exhausted coupons
    - Test submit_answer_route: mock save_answer/get_question, verify regular/ranking answers, missing fields
    - Test delete_answer_route: mock delete_answer, verify success and missing question_number
    - Test get_progress: mock load_answers, verify progress calculation
    - Test complete_questionnaire: mock load_answers/calculate_pdn_code/UserMetadataHandler, verify PDN code and CSV update
    - Test get_report_data: mock load_answers/calculate_pdn_code, verify report structure
    - Test _send_admin_notification: mock send_email_via_smtp/threading.Thread, verify non-blocking dispatch
    - Test save error returns HTTP 500
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9_

  - [x] 11.5 Write property test for diagnosis progress calculation in tests/test_diagnosis_routes_coverage.py
    - **Property 21: Diagnosis Progress Calculation**
    - Set of answers with numeric keys → current_question = max key; empty → 0
    - **Validates: Requirements 12.5**

- [x] 12. Final Checkpoint and Coverage Verification
  - [x] 12.1 Run full coverage report and verify ≥90% threshold
    - Execute: `pytest tests/ --cov=app/pdn_admin --cov=app/pdn_chat_ai --cov=app/pdn_relationships --cov=app/pdn_diagnose --cov-report=term-missing --cov-fail-under=90`
    - Verify per-file line coverage for all 13 target source files
    - Identify and fix any files below 90% threshold
    - _Requirements: 14.1, 14.2, 14.3_

  - [x] 12.2 Verify external dependency isolation
    - Confirm no LLM API calls (ChatAnthropic.invoke, ChatOpenAI.invoke) are unmocked
    - Confirm no email functions (send_email_via_smtp, send_pdn_code_email, send_binat_invite_email) are unmocked
    - Confirm no file I/O mutations occur during test execution
    - Confirm no threads are spawned (threading.Thread mocked)
    - _Requirements: 13.1, 13.2, 13.3, 13.4_

  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All tests extend existing test files — no new test files are created
- The `conftest.py` mock_env fixture is available for all tests
- External dependencies (LLM, email, file I/O, threading) must be fully mocked in every test

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "4.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5", "4.2", "4.3", "4.4", "4.5"] },
    { "id": 3, "tasks": ["5.1", "5.3", "5.4"] },
    { "id": 4, "tasks": ["5.2", "5.5", "5.6", "7.1"] },
    { "id": 5, "tasks": ["7.2", "7.3", "7.4", "7.5", "8.1"] },
    { "id": 6, "tasks": ["8.2", "8.3", "8.4", "8.5", "8.6"] },
    { "id": 7, "tasks": ["10.1", "10.2", "11.1", "11.4"] },
    { "id": 8, "tasks": ["10.3", "10.4", "11.2", "11.3", "11.5"] },
    { "id": 9, "tasks": ["12.1", "12.2"] }
  ]
}
```
