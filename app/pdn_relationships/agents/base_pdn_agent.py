"""BasePDNAgent - Shared base class for all PDN-based chat agents.

Extracts common LLM initialization, history management, usage tracking,
and summarization logic from PDNAgent. Enables future modules
(relationship advisor, parent-child, family dynamics) with minimal duplication.
"""

import json
import logging
import os
import re
import time

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.utils.user_history_service import UserHistoryService
from config import Config


# Retryable exceptions from LLM providers
try:
    from anthropic import RateLimitError as AnthropicRateLimitError, APITimeoutError as AnthropicTimeoutError
except ImportError:
    AnthropicRateLimitError = Exception
    AnthropicTimeoutError = Exception

try:
    from openai import RateLimitError as OpenAIRateLimitError, APITimeoutError as OpenAITimeoutError
except ImportError:
    OpenAIRateLimitError = Exception
    OpenAITimeoutError = Exception

# Pattern to detect prompt injection attempts in user input
_INJECTION_PATTERNS = re.compile(
    r'</?(system|context|user_message|assistant|instruction)>',
    re.IGNORECASE,
)

@dataclass
class UserHistory:
    """Per-user conversation history with raw exchanges and summary."""
    raw: List[dict] = field(default_factory=list)
    summary: str = ""


@dataclass
class BaseAgentConfig:
    """Configuration shared across all PDN-based agent variants."""
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    max_context_tokens: int = 3500
    max_turns_before_summary: int = 6
    raw_turns_to_keep: int = 3
    max_conversations_per_day: int = 15
    max_summary_tokens: int = 500


class BasePDNAgent:
    """Shared base class for all PDN-based chat agents.

    Provides:
    - LLM initialization (ChatAnthropic or ChatOpenAI based on config)
    - Conversation history management with hybrid summarization
    - Daily usage limit enforcement
    - Token usage tracking with disk persistence
    - User email registration for history persistence
    - Session persistence on logout
    """

    EXEMPT_USERS = frozenset(['פנינה'])  # Users exempt from daily limits

    def __init__(self, config: BaseAgentConfig = None):
        """Initialize the base PDN agent.

        Args:
            config: Agent configuration. Uses defaults if None.
        """
        if config is None:
            config = BaseAgentConfig()

        app_config = Config()

        # LLM configuration
        self.llm_provider = config.llm_provider or app_config.LLM_PROVIDER
        self.model_name = config.model_name or (
            app_config.ANTHROPIC_MODEL
            if self.llm_provider.lower() == 'anthropic'
            else app_config.OPENAI_MODEL
        )
        self.llm = self._initialize_llm(app_config)
        self._is_anthropic = self.llm_provider.lower() == 'anthropic'

        # Use a cheap model for summarization — same provider as main LLM
        # Note: claude-sonnet-5 doesn't support temperature parameter
        if self._is_anthropic:
            self.summary_llm = ChatAnthropic(
                model="claude-sonnet-5",
                api_key=app_config.ANTHROPIC_API_KEY,
            )
        else:
            self.summary_llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                api_key=app_config.OPENAI_API_KEY,
            )

        # Summarization / history thresholds
        self.MAX_CONTEXT_TOKENS = config.max_context_tokens
        self.MAX_TURNS_BEFORE_SUMMARY = config.max_turns_before_summary
        self.RAW_TURNS_TO_KEEP = config.raw_turns_to_keep
        self.MAX_CONVERSATIONS_PER_DAY = config.max_conversations_per_day
        self.MAX_SUMMARY_TOKENS = config.max_summary_tokens

        # Conversation state
        self.conversation_history: Dict[str, UserHistory] = defaultdict(UserHistory)
        self.user_conversations: Dict[str, dict] = defaultdict(
            lambda: {'count': 0, 'last_reset': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}
        )

        # Map display name → email for history persistence
        self._user_email_map: Dict[str, str] = {}

        # Token usage tracking — persisted to file with daily granularity
        self._usage_file = Path(os.getenv('SAVED_RESULTS_DIR', 'saved_results')) / 'token_usage.json'
        self.token_usage = self._load_usage_file()
        self._last_usage_save = 0  # timestamp of last disk write
        self._usage_save_interval = 5  # seconds between disk writes

        # User history persistence service
        self.history_service = UserHistoryService(
            base_dir=str(Path(os.getenv('SAVED_RESULTS_DIR', 'saved_results')))
        )

        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(
            "Initialized %s with %s using model %s",
            self.__class__.__name__, self.llm_provider, self.model_name,
        )

    def _initialize_llm(self, config) -> Union[ChatAnthropic, ChatOpenAI]:
        """Initialize the appropriate LLM based on the provider."""
        providers = {
            'anthropic': (ChatAnthropic, config.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY"),
            'openai': (ChatOpenAI, config.OPENAI_API_KEY, "OPENAI_API_KEY"),
        }

        provider_key = self.llm_provider.lower() if self.llm_provider.lower() in providers else 'openai'
        llm_class, api_key, key_name = providers[provider_key]

        if not api_key:
            raise ValueError(f"{key_name} not set")

        # Claude Sonnet 5 doesn't support temperature parameter
        kwargs = {
            "model": self.model_name,
            "max_tokens": 1500,
            "api_key": api_key,
            "timeout": 180,
        }
        # Only add temperature for models that support it (not claude-sonnet-5)
        if not self.model_name.startswith("claude-sonnet-5"):
            kwargs["temperature"] = 0.7
        
        return llm_class(**kwargs)

    def _build_system_message(self, system_prompt: str) -> SystemMessage:
        """Build a SystemMessage, adding Anthropic cache_control when applicable.

        Anthropic caches the system prompt server-side for 5 minutes.
        Subsequent calls with the same prompt pay only 10% of the input token cost.

        Note: cache_control must be on a content block (dict), not on additional_kwargs,
        because langchain-anthropic only reads cache_control from content blocks.
        """
        if self._is_anthropic:
            return SystemMessage(
                content=[{
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }]
            )
        return SystemMessage(content=system_prompt)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        retry=retry_if_exception_type((
            AnthropicRateLimitError, AnthropicTimeoutError,
            OpenAIRateLimitError, OpenAITimeoutError,
            TimeoutError, ConnectionError,
        )),
        reraise=True,
    )
    def _invoke_llm(self, messages, **kwargs):
        """Invoke the LLM with automatic retry on transient failures.

        Retries up to 3 times with exponential backoff (1s, 2s, 4s) on:
        - Rate limit errors (429)
        - Timeout errors
        - Connection errors
        """
        return self.llm.invoke(messages, **kwargs)

    @staticmethod
    def _sanitize_user_input(text: str) -> str:
        """Sanitize user input to prevent prompt injection.

        Strips XML-like tags that could break the prompt structure
        (e.g., </user_message>, <system>, etc.).
        """
        if not text:
            return text
        # Replace injection-like tags with escaped versions
        return _INJECTION_PATTERNS.sub(
            lambda m: m.group(0).replace('<', '＜').replace('>', '＞'),
            text,
        )

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count. Hebrew tokenizes at ~1 token per 2-3 chars."""
        return len(text) // 3

    def _format_history(self, user_name: str) -> str:
        """Format conversation history with summary + recent exchanges."""
        hist = self.conversation_history.get(user_name)
        if not hist or (not hist.raw and not hist.summary):
            return ""

        parts = []
        if hist.summary:
            parts.append(f"Previous conversation summary:\n{hist.summary}")

        if hist.raw:
            recent = "\n\n".join(
                f"User: {ex['user']}\nAssistant: {ex['assistant']}" for ex in hist.raw
            )
            parts.append(f"Recent exchanges:\n{recent}")

        return "\n\n".join(parts)

    def _add_to_history(self, user_name: str, user_query: str, assistant_response: str):
        """Add conversation exchange to history with hybrid summarization."""
        hist = self.conversation_history[user_name]
        hist.raw.append({"user": user_query, "assistant": assistant_response})

        # Calculate total tokens
        total_tokens = sum(
            self._estimate_tokens(ex['user']) + self._estimate_tokens(ex['assistant'])
            for ex in hist.raw
        )

        # Check both conditions
        turn_limit_reached = len(hist.raw) >= self.MAX_TURNS_BEFORE_SUMMARY
        token_limit_reached = total_tokens > self.MAX_CONTEXT_TOKENS

        # Summarize if either condition is met
        if turn_limit_reached or token_limit_reached:
            reason = "turn limit" if turn_limit_reached else "token limit"
            self.logger.info(
                "Summarizing for %s: %s reached (turns=%d, tokens=%d)",
                user_name, reason, len(hist.raw), total_tokens,
            )
            self._summarize_old_turns(user_name)

    def _summarize_old_turns(self, user_name: str) -> None:
        """Summarize old exchanges into a single consolidated narrative with token budget."""
        hist = self.conversation_history[user_name]
        if len(hist.raw) <= self.RAW_TURNS_TO_KEEP:
            return

        old_turns = hist.raw[:-self.RAW_TURNS_TO_KEEP]
        text = "\n".join(
            f"User: {ex['user']}\nAssistant: {ex['assistant']}" for ex in old_turns
        )
        today = datetime.now().strftime('%Y-%m-%d')

        # Build context for the LLM: existing summary + new turns
        if hist.summary:
            merge_input = (
                f"EXISTING SUMMARY:\n{hist.summary}\n\n"
                f"NEW CONVERSATION (date: {today}):\n{text}"
            )
            prompt = self._get_merge_prompt()
        else:
            merge_input = f"CONVERSATION (date: {today}):\n{text}"
            prompt = self._get_initial_prompt()

        try:
            consolidated = self.summary_llm.invoke(
                [SystemMessage(content=prompt), HumanMessage(content=merge_input)],
                max_tokens=self.MAX_SUMMARY_TOKENS,
            ).content

            hist.summary = consolidated.strip()
            # Persist history to disk for cross-session continuity (use email, not display name)
            persist_id = self._user_email_map.get(user_name, user_name)
            if hist.summary:
                self.history_service.save_user_history(
                    persist_id, hist.summary,
                    metadata={
                        "source": self.__class__.__name__,
                        "summary_version": "3",
                        "last_session_date": today,
                    },
                )
            hist.raw = hist.raw[-self.RAW_TURNS_TO_KEEP:]
            self.logger.info("Summarized %d turns for %s", len(old_turns), user_name)
        except Exception as e:
            # Summarization failed — truncate if too large to prevent unbounded growth
            self.logger.warning(
                "Summarization failed for %s, keeping raw history: %s", user_name, e
            )
            if len(hist.raw) > self.RAW_TURNS_TO_KEEP * 2:
                hist.raw = hist.raw[-self.RAW_TURNS_TO_KEEP:]

    def _get_merge_prompt(self) -> str:
        """Return the prompt for merging existing summary with new conversation."""
        return (
            "You are a personal development coach's memory system. "
            "Merge the EXISTING SUMMARY with the NEW CONVERSATION into ONE consolidated summary.\n\n"
            "FORMAT — produce exactly these sections:\n"
            "נושאים מרכזיים: [main topics/challenges discussed across all sessions]\n"
            "פרטים חשובים: [specific names, numbers, decisions — NEVER drop concrete details]\n"
            "מסע רגשי: [how the user's feelings evolved over time]\n"
            "החלטות ופעולות: [what was decided, what actions were taken or planned]\n"
            "לא נפתר: [open questions, unresolved tensions]\n"
            "סטטוס נוכחי: [where the user left off, what they plan to do next]\n\n"
            "RULES:\n"
            "- ONE consolidated narrative per section, not separate blocks per session\n"
            "- NEVER drop specific numbers, names, prices, or decisions\n"
            "- Include dates when things happened (e.g., 'ב-5.5 החליט...')\n"
            "- Prioritize recent/unresolved items over old resolved ones\n"
            "- If summary is getting long, compress OLD RESOLVED items, keep RECENT ones detailed\n"
            "- Max 10 lines total. Use Hebrew.\n"
            "- If the user spoke English about specific topics, keep those terms in English"
        )

    def _get_initial_prompt(self) -> str:
        """Return the prompt for creating the first summary from a conversation."""
        return (
            "You are a personal development coach's memory system. "
            "Summarize this conversation into a structured memory.\n\n"
            "FORMAT:\n"
            "נושאים מרכזיים: [main topics/challenges]\n"
            "פרטים חשובים: [specific names, numbers, decisions]\n"
            "מסע רגשי: [user's emotional state and why]\n"
            "החלטות ופעולות: [what was decided or planned]\n"
            "סטטוס נוכחי: [where the user left off]\n\n"
            "RULES:\n"
            "- Keep specific details: numbers, names, prices, dates\n"
            "- Max 8 lines. Use Hebrew.\n"
            "- If the user spoke English about specific topics, keep those terms"
        )

    def _reset_daily_count(self, user_name: str):
        """Reset the daily conversation count at midnight."""
        now = datetime.now()
        user_data = self.user_conversations[user_name]
        # Reset count if a new day has started
        if now.date() > user_data['last_reset'].date():
            old_date = user_data['last_reset'].date()
            user_data['count'] = 0
            user_data['last_reset'] = now
            self.logger.info(
                "Daily count for %s has been reset. Previous: %s, Current: %s",
                user_name, old_date, now.date(),
            )

    def _has_exceeded_daily_limit(self, user_name: str, max_conversations_per_day: int = None) -> bool:
        """Check if the user has exceeded the daily conversation limit."""
        self._reset_daily_count(user_name)

        if user_name not in self.EXEMPT_USERS:
            limit = max_conversations_per_day or self.MAX_CONVERSATIONS_PER_DAY
            return self.user_conversations[user_name]['count'] >= limit
        else:
            return False

    def _increment_conversation_count(self, user_name: str):
        """Increment the conversation count for the user."""
        self.user_conversations[user_name]['count'] += 1
        self.logger.info(
            "Incremented conversation count for %s. Current count: %d",
            user_name, self.user_conversations[user_name]['count'],
        )

    def _load_usage_file(self) -> dict:
        """Load token usage history from JSON file."""
        try:
            if self._usage_file.exists():
                with open(self._usage_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning("Could not load token usage file: %s", e)
        return {}

    def _save_usage_file(self, force: bool = False):
        """Persist token usage history to JSON file (debounced, atomic write)."""
        now = time.time()
        if not force and (now - self._last_usage_save) < self._usage_save_interval:
            return
        try:
            self._usage_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self._usage_file.with_suffix('.tmp')
            with open(tmp_file, 'w') as f:
                json.dump(self.token_usage, f, ensure_ascii=False, indent=2)
            tmp_file.replace(self._usage_file)
            self._last_usage_save = now
        except Exception as e:
            self.logger.warning("Could not save token usage file: %s", e)

    def _track_usage(self, user_name: str, response):
        """Extract and accumulate token usage from an LLM response, stored per user per day."""
        if not user_name:
            return
        usage = getattr(response, 'usage_metadata', None)
        if not usage:
            return

        # Handle both dict (OpenAI) and object (Anthropic) formats
        def get_val(obj, key, default=0):
            if isinstance(obj, dict):
                return obj.get(key, default) or default
            return getattr(obj, key, default) or default

        today = datetime.now().strftime('%Y-%m-%d')

        if user_name not in self.token_usage:
            self.token_usage[user_name] = {}
        if today not in self.token_usage[user_name]:
            self.token_usage[user_name][today] = {
                'input_tokens': 0, 'output_tokens': 0,
                'cache_creation_tokens': 0, 'cache_read_tokens': 0,
                'calls': 0, 'model': '',
            }

        day = self.token_usage[user_name][today]
        day['input_tokens'] += get_val(usage, 'input_tokens')
        day['output_tokens'] += get_val(usage, 'output_tokens')
        day['calls'] += 1
        day['model'] = self.model_name

        # Track cache tokens from input_token_details
        details = get_val(usage, 'input_token_details', None)
        if details:
            day['cache_creation_tokens'] += get_val(details, 'cache_creation')
            day['cache_read_tokens'] += get_val(details, 'cache_read')

        self._save_usage_file()

    def register_user_email(self, user_name: str, email: str) -> None:
        """Register the email for a display name so history can be persisted by email."""
        if user_name and email:
            self._user_email_map[user_name] = email

    def persist_session(self, user_name: str, email: str) -> None:
        """Force-save all conversation history for a user (called on logout).

        Summarizes any remaining raw turns and persists the result to disk.
        """
        if not user_name or not email:
            return
        self.register_user_email(user_name, email)
        hist = self.conversation_history.get(user_name)
        if not hist:
            return

        if hist.raw:
            # Summarize ALL remaining turns (bypass threshold)
            old_turns = hist.raw
            text = "\n".join(
                f"User: {ex['user']}\nAssistant: {ex['assistant']}" for ex in old_turns
            )
            today = datetime.now().strftime('%Y-%m-%d')

            if hist.summary:
                merge_input = (
                    f"EXISTING SUMMARY:\n{hist.summary}\n\n"
                    f"NEW CONVERSATION (date: {today}):\n{text}"
                )
                prompt = self._get_merge_prompt()
            else:
                merge_input = f"CONVERSATION (date: {today}):\n{text}"
                prompt = self._get_initial_prompt()

            try:
                consolidated = self.summary_llm.invoke(
                    [SystemMessage(content=prompt), HumanMessage(content=merge_input)],
                    max_tokens=self.MAX_SUMMARY_TOKENS,
                ).content
                hist.summary = consolidated.strip()
                hist.raw = []
            except Exception as e:
                self.logger.warning(
                    "Logout summarization failed for %s: %s", user_name, e
                )

        # Persist whatever summary we have
        if hist.summary:
            self.history_service.save_user_history(
                email, hist.summary,
                metadata={
                    "source": self.__class__.__name__,
                    "summary_version": "3",
                    "last_session_date": datetime.now().strftime('%Y-%m-%d'),
                },
            )

    def clear_user_history(self, user_name: str):
        """Clear conversation history for user."""
        if user_name in self.conversation_history:
            self.conversation_history[user_name] = UserHistory()
