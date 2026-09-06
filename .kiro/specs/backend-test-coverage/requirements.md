# Requirements Document

## Introduction

This specification defines the requirements for achieving at least 90% code coverage across four backend modules in the PDN Chat application: `pdn_admin`, `pdn_chat_ai`, `pdn_relationships`, and `pdn_diagnose`. Tests extend existing test files using pytest, unittest.mock, and hypothesis, with all external dependencies (LLM calls, file I/O, email sending) fully mocked.

## Glossary

- **Test_Suite**: The collection of pytest test functions covering a specific module
- **Coverage_Tool**: pytest-cov, the code coverage measurement plugin for pytest
- **Mock**: A unittest.mock object that replaces an external dependency during testing
- **Property_Test**: A hypothesis-based test that verifies behavior across generated inputs
- **Admin_Module**: The `app/pdn_admin` package containing admin_routes.py, audio_routes.py, and coupon_manager.py
- **Chat_AI_Module**: The `app/pdn_chat_ai` package containing chat_routes.py, logger.py, user_manager.py, and binat_agents/pdn_agent.py
- **Relationships_Module**: The `app/pdn_relationships` package containing constants.py, relationship_routes.py, agents/base_pdn_agent.py, and agents/relationship_agent.py
- **Diagnose_Module**: The `app/pdn_diagnose` package containing diagnosis_routes.py
- **External_Dependency**: Any component that performs LLM API calls, file system I/O, email sending, or network requests
- **Branch_Coverage**: The percentage of code branches (if/else, try/except, conditional expressions) exercised by tests

## Requirements

### Requirement 1: Admin Module Route Coverage

**User Story:** As a developer, I want comprehensive tests for admin_routes.py, so that session management, user metadata, CRUD operations, and email sending are verified without relying on external services.

#### Acceptance Criteria

1. WHEN the Test_Suite for admin_routes.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for admin_routes.py
2. WHEN admin login is tested, THE Test_Suite SHALL mock the Flask app config for ADMIN_PASSWORD and verify both successful and failed login responses
3. WHEN session management functions are tested, THE Test_Suite SHALL verify create_session, verify_session, cleanup_expired_sessions, and the require_admin_session decorator
4. WHEN user metadata endpoints are tested, THE Test_Suite SHALL mock UserMetadataHandler and CSV file reads to verify load_user_metadata, get_user_questionnaire, and get_user_voice
5. WHEN email-sending endpoints are tested, THE Test_Suite SHALL mock send_pdn_code_email and send_binat_invite_email to verify send_user_email and send_binat_invite without network calls
6. WHEN PDN recalculation is tested, THE Test_Suite SHALL mock load_answers and calculate_pdn_code to verify recalculate_user_pdn returns correct response structures
7. WHEN audio file serving is tested, THE Test_Suite SHALL mock file system access and verify path traversal protection in serve_audio
8. IF an endpoint receives invalid input, THEN THE Test_Suite SHALL verify the endpoint returns the appropriate HTTP 400 or 404 error response

### Requirement 2: Admin Audio Routes Coverage

**User Story:** As a developer, I want comprehensive tests for audio_routes.py, so that audio file serving with range requests is verified without accessing the file system.

#### Acceptance Criteria

1. WHEN the Test_Suite for audio_routes.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for audio_routes.py
2. WHEN a full audio file request is tested, THE Test_Suite SHALL mock file system access and verify the response returns audio/wav content with status 200
3. WHEN a range request is tested, THE Test_Suite SHALL verify the response returns status 206 with correct Content-Range headers
4. IF the requested audio file does not exist, THEN THE Test_Suite SHALL verify the endpoint returns HTTP 404
5. IF the range header contains invalid values, THEN THE Test_Suite SHALL verify the endpoint returns HTTP 416
6. IF the audio file is empty (zero bytes), THEN THE Test_Suite SHALL verify the endpoint returns HTTP 404

### Requirement 3: Coupon Manager Coverage

**User Story:** As a developer, I want comprehensive tests for coupon_manager.py, so that coupon CRUD operations, validation, and redemption logic are verified with mocked file persistence.

#### Acceptance Criteria

1. WHEN the Test_Suite for coupon_manager.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for coupon_manager.py
2. WHEN coupon creation is tested, THE Test_Suite SHALL verify both auto-generated and custom code paths, including duplicate code rejection
3. WHEN coupon validation is tested, THE Test_Suite SHALL verify valid coupons, exhausted coupons, and non-existent codes
4. WHEN validate_and_redeem is tested, THE Test_Suite SHALL verify atomic validation and redemption in a single operation, including email deduplication in used_by
5. WHEN coupon update is tested, THE Test_Suite SHALL verify allowed field updates and rejection of immutable code field changes
6. WHEN coupon deletion is tested, THE Test_Suite SHALL verify successful deletion and KeyError for non-existent codes
7. THE Test_Suite SHALL mock JSON file I/O so that _save_to_file and _load_initial_data execute without touching the file system
8. WHEN generate_coupon_code is tested, THE Test_Suite SHALL verify uniqueness against existing codes and proper character set usage

### Requirement 4: Chat Routes Coverage

**User Story:** As a developer, I want comprehensive tests for chat_routes.py, so that login, logout, chat messaging, 21-day plan, and daily training endpoints are verified with mocked LLM calls.

#### Acceptance Criteria

1. WHEN the Test_Suite for chat_routes.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for chat_routes.py
2. WHEN login is tested, THE Test_Suite SHALL mock get_user_manager to verify successful login, failed login, and missing field scenarios
3. WHEN chat messaging is tested, THE Test_Suite SHALL mock the PDNAgent.chat_with_binat method to verify message validation, conversation stats tracking, and response formatting
4. WHEN the 21-day plan endpoint is tested, THE Test_Suite SHALL mock PDNAgent.build_21_transformation_plan to verify goal validation and response structure
5. WHEN daily training is tested, THE Test_Suite SHALL mock PDNAgent.daily_training to verify task validation and response structure
6. WHEN logout is tested, THE Test_Suite SHALL verify conversation history persistence via agent.persist_session and session clearing
7. WHEN the handle_errors decorator encounters exceptions, THE Test_Suite SHALL verify differentiated HTTP status codes for ValidationError (400), AuthenticationError (401), RateLimitExceeded (429), TimeoutError (503), and generic Exception (500)
8. IF a chat message exceeds 5000 characters, THEN THE Test_Suite SHALL verify the endpoint returns HTTP 400 with a validation error

### Requirement 5: Logger Module Coverage

**User Story:** As a developer, I want comprehensive tests for logger.py, so that logger setup, handler configuration, and idempotent behavior are verified.

#### Acceptance Criteria

1. WHEN the Test_Suite for logger.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for logger.py
2. WHEN setup_logger is called with a name, THE Test_Suite SHALL verify the returned logger has the correct name, level, and handler configuration
3. WHEN setup_logger is called multiple times with the same name, THE Test_Suite SHALL verify no duplicate handlers are added (idempotent behavior)

### Requirement 6: User Manager Coverage

**User Story:** As a developer, I want comprehensive tests for user_manager.py, so that user CRUD, password hashing, email validation, and PDN code validation are verified with mocked file persistence.

#### Acceptance Criteria

1. WHEN the Test_Suite for user_manager.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for user_manager.py
2. WHEN add_user is tested, THE Test_Suite SHALL verify successful creation, duplicate email rejection, invalid email format rejection, and invalid PDN code rejection
3. WHEN verify_password is tested, THE Test_Suite SHALL verify correct password acceptance, incorrect password rejection, and non-existent user handling with timing-safe comparison
4. WHEN update_user is tested, THE Test_Suite SHALL verify allowed field updates, password re-hashing, and validation of pdn_code, daily_conversation_limit, name, and gender fields
5. WHEN delete_user is tested, THE Test_Suite SHALL verify successful deletion and KeyError for non-existent users
6. WHEN _migrate_plaintext_passwords is tested, THE Test_Suite SHALL verify plaintext passwords are converted to bcrypt hashes on initialization
7. THE Test_Suite SHALL mock JSON file I/O so that _save_to_file and _load_users execute without touching the file system
8. WHEN get_available_pdn_codes is tested, THE Test_Suite SHALL mock the PROMPTS_DIR filesystem to verify code discovery from .prompt files

### Requirement 7: PDN Agent Coverage

**User Story:** As a developer, I want comprehensive tests for pdn_agent.py, so that chat_with_binat, build_21_transformation_plan, daily_training, prompt loading, and usage stats are verified with mocked LLM calls.

#### Acceptance Criteria

1. WHEN the Test_Suite for pdn_agent.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for pdn_agent.py
2. WHEN chat_with_binat is tested, THE Test_Suite SHALL mock _invoke_llm to verify prompt composition, history formatting, input sanitization, and daily limit enforcement
3. WHEN build_21_transformation_plan is tested, THE Test_Suite SHALL mock _invoke_llm to verify goal-based prompt construction and response handling
4. WHEN daily_training is tested, THE Test_Suite SHALL mock _invoke_llm to verify task-based prompt construction and response handling
5. WHEN _load_prompt is tested, THE Test_Suite SHALL mock file reads to verify prompt caching, guardrails inclusion, and ValueError for invalid PDN codes
6. WHEN get_usage_stats is tested, THE Test_Suite SHALL provide synthetic token_usage data and verify cost calculations, model comparisons, projections, and recommendations
7. WHEN _clean_response is tested, THE Test_Suite SHALL verify removal of internal prompt markers from user-facing responses
8. IF a user has exceeded the daily conversation limit, THEN THE Test_Suite SHALL verify the agent returns the daily limit message without invoking the LLM

### Requirement 8: Base PDN Agent Coverage

**User Story:** As a developer, I want comprehensive tests for base_pdn_agent.py, so that LLM initialization, conversation history management, summarization, daily limits, token tracking, and session persistence are verified with mocked LLM calls.

#### Acceptance Criteria

1. WHEN the Test_Suite for base_pdn_agent.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for base_pdn_agent.py
2. WHEN _initialize_llm is tested, THE Test_Suite SHALL mock API keys and verify both Anthropic and OpenAI provider initialization paths
3. WHEN _add_to_history is tested, THE Test_Suite SHALL verify turn accumulation, summarization trigger by turn limit, and summarization trigger by token limit
4. WHEN _summarize_old_turns is tested, THE Test_Suite SHALL mock the summary_llm to verify summary generation, history truncation, and persistence via UserHistoryService
5. WHEN _has_exceeded_daily_limit is tested, THE Test_Suite SHALL verify limit enforcement, daily reset logic, and exempt user bypass
6. WHEN _track_usage is tested, THE Test_Suite SHALL verify per-user per-day token accumulation and file persistence debouncing
7. WHEN persist_session is tested, THE Test_Suite SHALL mock summary_llm to verify forced summarization of remaining raw turns and disk persistence
8. WHEN _sanitize_user_input is tested, THE Test_Suite SHALL verify prompt injection patterns are neutralized
9. WHEN _build_system_message is tested, THE Test_Suite SHALL verify Anthropic cache_control inclusion and OpenAI plain SystemMessage construction
10. IF summarization fails due to an LLM error, THEN THE Test_Suite SHALL verify graceful fallback with history truncation

### Requirement 9: Relationship Agent Coverage

**User Story:** As a developer, I want comprehensive tests for relationship_agent.py, so that relationship-specific chat, prompt composition, and code data loading are verified with mocked LLM calls and file reads.

#### Acceptance Criteria

1. WHEN the Test_Suite for relationship_agent.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for relationship_agent.py
2. WHEN chat is tested, THE Test_Suite SHALL mock _invoke_llm to verify prompt composition includes both user and partner PDN codes, relationship type label, and history context
3. WHEN _load_relationship_prompt is tested, THE Test_Suite SHALL mock file reads to verify composition order (base prompt, guardrails, relationship context, user code, partner code) and caching behavior
4. WHEN _load_code_data is tested, THE Test_Suite SHALL verify successful file loading and ValueError for empty or unknown PDN codes
5. IF a user has exceeded the daily conversation limit, THEN THE Test_Suite SHALL verify the agent returns DAILY_LIMIT_MESSAGE without invoking the LLM

### Requirement 10: Relationship Routes Coverage

**User Story:** As a developer, I want comprehensive tests for relationship_routes.py, so that login, chat, logout, and error handling are verified with mocked agent and user manager.

#### Acceptance Criteria

1. WHEN the Test_Suite for relationship_routes.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for relationship_routes.py
2. WHEN login is tested, THE Test_Suite SHALL mock get_user_manager to verify successful login with valid partner_code and relationship_type, and rejection of invalid codes or types
3. WHEN chat is tested, THE Test_Suite SHALL mock get_relationship_agent to verify message validation, conversation stats tracking, history injection, and response formatting
4. WHEN logout is tested, THE Test_Suite SHALL verify agent.persist_session is called and session is cleared
5. WHEN the handle_errors decorator encounters exceptions, THE Test_Suite SHALL verify differentiated HTTP status codes for ValueError (400), TimeoutError (503), and generic Exception (500)
6. IF a chat message exceeds 5000 characters, THEN THE Test_Suite SHALL verify the endpoint returns HTTP 400

### Requirement 11: Relationship Constants Coverage

**User Story:** As a developer, I want tests for constants.py, so that the RelationshipType enum and PDN_CODES list are verified for correctness.

#### Acceptance Criteria

1. WHEN the Test_Suite for constants.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for constants.py
2. THE Test_Suite SHALL verify RelationshipType enum contains exactly the values "partner", "friend", and "colleague"
3. THE Test_Suite SHALL verify PDN_CODES contains exactly 12 codes matching the expected pattern

### Requirement 12: Diagnosis Routes Coverage

**User Story:** As a developer, I want comprehensive tests for diagnosis_routes.py, so that login, questionnaire flow, answer submission, progress tracking, and report generation are verified with mocked dependencies.

#### Acceptance Criteria

1. WHEN the Test_Suite for diagnosis_routes.py executes, THE Coverage_Tool SHALL report at least 90% line coverage for diagnosis_routes.py
2. WHEN login is tested, THE Test_Suite SHALL verify both email/password and coupon-based authentication paths, including invalid credentials and exhausted coupons
3. WHEN submit_answer_route is tested, THE Test_Suite SHALL mock save_answer and get_question to verify regular answers, ranking answers, and missing field validation
4. WHEN delete_answer_route is tested, THE Test_Suite SHALL mock delete_answer to verify successful deletion and missing question_number handling
5. WHEN get_progress is tested, THE Test_Suite SHALL mock load_answers to verify progress calculation from saved answers
6. WHEN complete_questionnaire is tested, THE Test_Suite SHALL mock load_answers, calculate_pdn_code, and UserMetadataHandler to verify PDN code calculation and CSV update
7. WHEN get_report_data is tested, THE Test_Suite SHALL mock load_answers and calculate_pdn_code to verify report data structure
8. WHEN _send_admin_notification is tested, THE Test_Suite SHALL mock send_email_via_smtp to verify non-blocking email dispatch
9. IF answer submission fails due to a save error, THEN THE Test_Suite SHALL verify the endpoint returns HTTP 500 with an appropriate error message

### Requirement 13: External Dependency Isolation

**User Story:** As a developer, I want all external dependencies fully mocked, so that tests run fast, deterministically, and without network or file system side effects.

#### Acceptance Criteria

1. THE Test_Suite SHALL mock all LLM API calls (ChatAnthropic.invoke, ChatOpenAI.invoke) so that no network requests are made during test execution
2. THE Test_Suite SHALL mock all email-sending functions (send_email_via_smtp, send_pdn_code_email, send_binat_invite_email) so that no SMTP connections are established
3. THE Test_Suite SHALL mock file I/O operations (JSON reads/writes, CSV reads, audio file access) so that no file system mutations occur during test execution
4. THE Test_Suite SHALL mock threading.Thread for background email notifications so that no threads are spawned during test execution

### Requirement 14: Coverage Measurement and Reporting

**User Story:** As a developer, I want a single pytest command that measures and reports coverage for all four modules, so that I can verify the 90% threshold is met.

#### Acceptance Criteria

1. WHEN pytest executes with coverage flags for the four target modules, THE Coverage_Tool SHALL produce a combined coverage report
2. THE Coverage_Tool SHALL report per-file line coverage for each of the 13 target source files
3. IF any target file has less than 90% line coverage, THEN THE Coverage_Tool SHALL indicate the file as below threshold in the report
