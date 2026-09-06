# Design Document: Backend Test Coverage

## Overview

This design specifies the architecture for achieving ≥90% line coverage across four backend modules (`pdn_admin`, `pdn_chat_ai`, `pdn_relationships`, `pdn_diagnose`) using pytest, unittest.mock, and hypothesis. Tests extend existing test files, fully mock external dependencies (LLM, email, file I/O), and include property-based tests for behaviors that vary meaningfully with input.

## Architecture

### Test Organization Strategy

Tests are organized by extending existing test files rather than creating new ones. Each module's tests follow a consistent pattern:

```
tests/
├── test_admin_routes_coverage.py      # Extended: session mgmt, metadata, email, audio
├── test_coupon_admin_routes.py        # Extended: coupon CRUD via routes
├── test_coupon_properties.py          # Extended: property tests for coupon logic
├── test_diagnosis_routes_coverage.py  # Extended: login, answers, progress, report
├── test_chat_routes.py                # Extended: login, chat, plan, training, logout
├── test_chat_improvements.py          # Extended: error handling, edge cases
├── test_user_manager.py              # Extended: CRUD, validation, migration
├── test_user_manager_coverage.py     # Extended: edge cases, password hashing
├── test_pdn_agent.py                 # Extended: chat methods, prompt loading, stats
├── test_pdn_agent_refactored.py      # Extended: clean_response, daily limits
├── test_pdn_agent_history.py         # Extended: history, summarization, persistence
├── test_relationship_routes.py       # Extended: login, chat, logout
├── test_property_relationship_routes.py  # Extended: property tests
├── test_relationship_agent.py        # Extended: chat, prompt loading
├── test_property_relationship_agent.py   # Extended: property tests
├── test_property_base_agent.py       # Extended: property tests for base agent
└── conftest.py                       # Provides mock_env fixture
```

### Mocking Strategy

All external dependencies are isolated using `unittest.mock.patch`:

```python
# LLM calls — mock at the invoke level
@patch.object(ChatAnthropic, 'invoke', return_value=mock_response)
@patch.object(ChatOpenAI, 'invoke', return_value=mock_response)

# Email — mock the sending functions
@patch('app.utils.email_sender.send_pdn_code_email', return_value=True)
@patch('app.utils.email_sender.send_binat_invite_email', return_value=True)
@patch('app.utils.email_sender.send_email_via_smtp')

# File I/O — mock Path operations and open()
@patch('pathlib.Path.exists', return_value=True)
@patch('pathlib.Path.read_text', return_value='mock content')
@patch('builtins.open', mock_open(read_data=b'audio data'))

# Threading — mock Thread to prevent spawning
@patch('threading.Thread')
```

### Flask Test Client Pattern

All route tests use Flask's test client with application context:

```python
import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret'
    app.config['ADMIN_PASSWORD'] = 'test-password'
    return app

@pytest.fixture
def client(app):
    return app.test_client()
```

### Hypothesis Strategy Definitions

Shared strategies for property-based tests:

```python
from hypothesis import strategies as st, given, settings

# Email strategy
emails = st.from_regex(r'[a-z]{3,10}@[a-z]{3,8}\.[a-z]{2,4}', fullmatch=True)

# PDN code strategy
pdn_codes = st.sampled_from([
    "a3", "a7", "a11", "e1", "e5", "e9",
    "p2", "p6", "p10", "t4", "t8", "t12"
])

# Coupon code strategy (valid custom codes: 4-20 alphanumeric)
coupon_codes = st.from_regex(r'[A-Za-z0-9]{4,20}', fullmatch=True)

# User message strategy (non-empty, within limits)
user_messages = st.text(min_size=1, max_size=5000)

# Token usage data strategy
token_usage_entry = st.fixed_dictionaries({
    'input_tokens': st.integers(min_value=0, max_value=100000),
    'output_tokens': st.integers(min_value=0, max_value=50000),
    'cache_creation_tokens': st.integers(min_value=0, max_value=50000),
    'cache_read_tokens': st.integers(min_value=0, max_value=50000),
    'calls': st.integers(min_value=1, max_value=100),
    'model': st.sampled_from(['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022', 'gpt-4o-mini']),
})
```

## Components and Interfaces

### 1. Admin Module Tests

**Target files:** `admin_routes.py`, `audio_routes.py`, `coupon_manager.py`

**Test files extended:**
- `test_admin_routes_coverage.py` — session management, metadata, email, PDN recalculation, audio serving
- `test_coupon_admin_routes.py` — coupon CRUD via admin routes
- `test_coupon_properties.py` — property tests for coupon logic

**Key mock targets:**
- `UserMetadataHandler` — CSV/JSON file operations
- `send_pdn_code_email`, `send_binat_invite_email` — email sending
- `load_answers`, `calculate_pdn_code` — answer storage and calculation
- `PDNFilePath` — file path resolution
- `Path.exists`, `os.path.getsize`, `open` — file system access

### 2. Chat AI Module Tests

**Target files:** `chat_routes.py`, `logger.py`, `user_manager.py`, `binat_agents/pdn_agent.py`

**Test files extended:**
- `test_chat_routes.py` — login, chat, 21-day plan, daily training, logout
- `test_chat_improvements.py` — error handling edge cases
- `test_user_manager.py` — CRUD, validation
- `test_user_manager_coverage.py` — password hashing, migration, edge cases
- `test_pdn_agent.py` — chat methods, prompt loading
- `test_pdn_agent_refactored.py` — clean_response, daily limits
- `test_pdn_agent_history.py` — history management, summarization

**Key mock targets:**
- `PDNAgent._invoke_llm` — LLM invocation
- `get_user_manager()` — user manager singleton
- `Path.read_text` — prompt file loading
- `json.loads`, `Path.write_text` — JSON persistence

### 3. Relationships Module Tests

**Target files:** `constants.py`, `relationship_routes.py`, `agents/base_pdn_agent.py`, `agents/relationship_agent.py`

**Test files extended:**
- `test_relationship_routes.py` — login, chat, logout
- `test_property_relationship_routes.py` — property tests for routes
- `test_relationship_agent.py` — chat, prompt loading
- `test_property_relationship_agent.py` — property tests for agent
- `test_property_base_agent.py` — property tests for base agent

**Key mock targets:**
- `BasePDNAgent._invoke_llm` — LLM invocation
- `BasePDNAgent.summary_llm.invoke` — summarization LLM
- `get_user_manager()` — user manager singleton
- `UserHistoryService` — history persistence
- `Path.read_text`, `Path.exists` — prompt file loading

### 4. Diagnose Module Tests

**Target files:** `diagnosis_routes.py`

**Test files extended:**
- `test_diagnosis_routes_coverage.py` — login, questionnaire flow, answers, progress, report

**Key mock targets:**
- `save_answer`, `load_answers`, `delete_answer` — answer storage
- `calculate_pdn_code` — PDN calculation
- `get_coupon_manager()` — coupon validation
- `send_email_via_smtp` — admin notifications
- `threading.Thread` — background email dispatch

### Coverage Command Interface

```bash
pytest tests/ \
  --cov=app/pdn_admin \
  --cov=app/pdn_chat_ai \
  --cov=app/pdn_relationships \
  --cov=app/pdn_diagnose \
  --cov-report=term-missing \
  --cov-fail-under=90
```

### Mock Response Factory

```python
class MockLLMResponse:
    """Factory for creating mock LLM responses with usage metadata."""
    
    def __init__(self, content: str = "Mock response",
                 input_tokens: int = 100, output_tokens: int = 50):
        self.content = content
        self.usage_metadata = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'input_token_details': {
                'cache_creation': 0,
                'cache_read': 0,
            }
        }
```

### Hypothesis Settings Profile

```python
from hypothesis import settings, HealthCheck

settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("ci")
```

## Data Models

### Test Fixtures Data

```python
# Sample user data for tests
SAMPLE_USER = {
    'email': 'test@example.com',
    'password': 'test-password',
    'name': 'Test User',
    'pdn_code': 'e5',
    'gender': 'male',
    'daily_conversation_limit': 15,
}

# Sample coupon data for tests
SAMPLE_COUPON = {
    'name': 'Test Coupon',
    'code': 'TESTCODE',
    'max_usage': 10,
    'usage_count': 0,
    'used_by': [],
    'created_at': '2025-01-01 00:00',
    'updated_at': '2025-01-01 00:00',
}

# Sample token usage data for tests
SAMPLE_TOKEN_USAGE = {
    'user1': {
        '2025-01-15': {
            'input_tokens': 5000,
            'output_tokens': 2000,
            'cache_creation_tokens': 1000,
            'cache_read_tokens': 3000,
            'calls': 10,
            'model': 'claude-sonnet-4-20250514',
        }
    }
}
```

## Error Handling

### Test Error Patterns

Each module's error handling is tested by:

1. **Input validation errors** — Empty fields, oversized messages, invalid formats → HTTP 400
2. **Authentication errors** — Invalid credentials, expired sessions → HTTP 401
3. **Not found errors** — Missing users, files, coupons → HTTP 404
4. **Rate limit errors** — Daily conversation limit exceeded → HTTP 429
5. **Network errors** — LLM timeout, connection failure → HTTP 503
6. **Internal errors** — Unexpected exceptions → HTTP 500

### Graceful Degradation Testing

```python
# Summarization failure fallback
def test_summarization_failure_truncates_history(agent):
    """When LLM summarization fails, history is truncated to prevent unbounded growth."""
    with patch.object(agent.summary_llm, 'invoke', side_effect=Exception("LLM error")):
        # Add enough turns to trigger summarization
        for i in range(agent.MAX_TURNS_BEFORE_SUMMARY + 1):
            agent._add_to_history("user", f"msg {i}", f"resp {i}")
        # History should be truncated, not crash
        assert len(agent.conversation_history["user"].raw) <= agent.RAW_TURNS_TO_KEEP * 2
```

## Testing Strategy

### Dual Testing Approach

- **Unit tests (example-based):** Verify specific scenarios for route endpoints (login success/failure, CRUD operations, error responses). These use Flask test client with mocked dependencies and cover the majority of route-level code.
- **Property tests (hypothesis):** Verify universal invariants across generated inputs for pure logic functions (coupon validation, password hashing, session management, cost calculations, input sanitization). Minimum 100 iterations per property.

### Test Execution

```bash
# Run all tests with coverage
pytest tests/ \
  --cov=app/pdn_admin \
  --cov=app/pdn_chat_ai \
  --cov=app/pdn_relationships \
  --cov=app/pdn_diagnose \
  --cov-report=term-missing \
  --cov-fail-under=90

# Run only property tests
pytest tests/ -k "property" --hypothesis-show-statistics
```

### Coverage Gaps Strategy

For each source file below 90%, the approach is:
1. Run `pytest --cov=<module> --cov-report=term-missing` to identify uncovered lines
2. Add tests targeting the specific uncovered branches (error paths, edge cases)
3. Re-run coverage to verify the gap is closed

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Session Lifecycle Validity

*For any* email string, creating a session should produce a token that passes verification, and after the session expires (time advanced past SESSION_TIMEOUT), verification should reject that same token.

**Validates: Requirements 1.3**

### Property 2: Path Traversal Protection

*For any* file path that resolves outside the allowed `SAVED_RESULTS_DIR` directory (e.g., containing `../` sequences), the `serve_audio` endpoint should reject the request with HTTP 403, never serving files outside the allowed directory.

**Validates: Requirements 1.7**

### Property 3: Audio Range Request Correctness

*For any* valid byte range `(start, end)` where `0 <= start <= end < file_size`, the audio endpoint should return HTTP 206 with a `Content-Range` header of `bytes {start}-{end}/{file_size}` and a response body of exactly `(end - start + 1)` bytes.

**Validates: Requirements 2.3**

### Property 4: Coupon Code Generation Uniqueness and Charset

*For any* set of existing coupon codes, `generate_coupon_code` should produce a code that is not in the existing set, consists only of uppercase ASCII letters and digits, and is exactly 8 characters long.

**Validates: Requirements 3.2, 3.8**

### Property 5: Coupon Validation Reflects Usage State

*For any* coupon with `usage_count` and `max_usage`, `validate_coupon` should return `(True, "Valid")` if and only if `usage_count < max_usage`, and `(False, "Coupon has reached its usage limit")` otherwise. For any code not in the coupon store, it should return `(False, "Invalid coupon code")`.

**Validates: Requirements 3.3**

### Property 6: Coupon Validate-and-Redeem Atomicity with Email Deduplication

*For any* valid coupon (usage_count < max_usage) and any email, `validate_and_redeem` should atomically increment `usage_count` by exactly 1 and ensure the email appears in `used_by` at most once regardless of how many times the same email redeems.

**Validates: Requirements 3.4**

### Property 7: Coupon Code Immutability on Update

*For any* coupon update request that includes a "code" field, `update_coupon` should raise `ValueError` regardless of the value provided, preserving the original code.

**Validates: Requirements 3.5**

### Property 8: Error Decorator Exception-to-Status Mapping

*For any* exception type in `{ValidationError → 400, AuthenticationError → 401, RateLimitExceeded → 429, TimeoutError → 503, Exception → 500}`, the `handle_errors` decorator should return the corresponding HTTP status code. Similarly for the relationship routes decorator: `{ValueError → 400, TimeoutError → 503, Exception → 500}`.

**Validates: Requirements 4.7, 10.5**

### Property 9: Logger Setup Idempotence

*For any* logger name and any number of repeated calls N ≥ 1, `setup_logger(name)` should return a logger with exactly one handler (no duplicates), and the handler should have the expected formatter pattern.

**Validates: Requirements 5.3**

### Property 10: User Creation Validation Rules

*For any* email that does not match the pattern `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`, `add_user` should raise `ValueError`. For any `pdn_code` not in the available codes list, `add_user` should raise `ValueError`. For any email already in the user store, `add_user` should raise `ValueError`.

**Validates: Requirements 6.2**

### Property 11: Password Hash Round-Trip

*For any* user created with password P, `verify_password(email, P)` should return `True`, and for any password Q ≠ P, `verify_password(email, Q)` should return `False`.

**Validates: Requirements 6.3**

### Property 12: User Update Validation Rules

*For any* `pdn_code` value not in the available codes list, `update_user(email, pdn_code=value)` should raise `ValueError`. For any `daily_conversation_limit` that is not a positive integer, `update_user` should raise `ValueError`. For any empty `name`, `update_user` should raise `ValueError`. For any `gender` not in `{'male', 'female', ''}`, `update_user` should raise `ValueError`.

**Validates: Requirements 6.4**

### Property 13: Plaintext Password Migration

*For any* user whose stored password does not start with `$2b$`, after `_migrate_plaintext_passwords` executes, the stored password should start with `$2b$` (bcrypt hash prefix) and the original plaintext password should still verify correctly.

**Validates: Requirements 6.6**

### Property 14: Prompt Loading Caching and Validation

*For any* valid PDN code and prompt file, calling `_load_prompt` (or `_load_relationship_prompt`) twice with the same arguments should return identical strings and only read files on the first call (cache hit on second). For any empty or non-existent PDN code, the function should raise `ValueError`.

**Validates: Requirements 7.5, 9.3, 9.4**

### Property 15: Usage Stats Cost Calculation Invariant

*For any* token usage data with `input_tokens`, `output_tokens`, `cache_creation_tokens`, and `cache_read_tokens`, the calculated cost should equal `(uncached_input/1e6 × input_price) + (output/1e6 × output_price) + (cache_creation/1e6 × cache_write_price) + (cache_read/1e6 × cache_read_price)` where `uncached_input = input_tokens - cache_creation_tokens - cache_read_tokens`.

**Validates: Requirements 7.6**

### Property 16: Response Marker Cleaning

*For any* string containing `[STOP` followed by any characters and `]`, `_clean_response` should produce a string that does not contain any such bracketed marker patterns, and the result should be stripped of leading/trailing whitespace.

**Validates: Requirements 7.7**

### Property 17: Daily Conversation Limit Enforcement

*For any* non-exempt user whose conversation count equals or exceeds their daily limit, `_has_exceeded_daily_limit` should return `True` and the agent should return the daily limit message without invoking the LLM. For any exempt user (in `EXEMPT_USERS`), the function should always return `False` regardless of count.

**Validates: Requirements 7.8, 8.5, 9.5**

### Property 18: Conversation History Summarization Lifecycle

*For any* sequence of conversation exchanges added via `_add_to_history`, when either the turn count reaches `MAX_TURNS_BEFORE_SUMMARY` or the estimated token count exceeds `MAX_CONTEXT_TOKENS`, summarization should trigger, resulting in `raw` history containing at most `RAW_TURNS_TO_KEEP` entries and a non-empty `summary` field.

**Validates: Requirements 8.3, 8.4**

### Property 19: Token Usage Accumulation Invariant

*For any* sequence of N LLM responses with usage metadata tracked via `_track_usage` for the same user on the same day, the stored `input_tokens` should equal the sum of all individual `input_tokens` values, `output_tokens` should equal the sum of all individual `output_tokens` values, and `calls` should equal N.

**Validates: Requirements 8.6**

### Property 20: Input Sanitization Neutralizes Injection Patterns

*For any* string containing XML-like tags matching the pattern `</?(system|context|user_message|assistant|instruction)>`, `_sanitize_user_input` should produce a string where all such tags have their angle brackets replaced with full-width equivalents (`＜`, `＞`), preventing prompt structure breakage.

**Validates: Requirements 8.8**

### Property 21: Diagnosis Progress Calculation

*For any* set of saved answers with numeric string keys, `get_progress` should return the maximum numeric key value as `current_question`. For an empty answer set or one with no numeric keys, it should return 0.

**Validates: Requirements 12.5**
