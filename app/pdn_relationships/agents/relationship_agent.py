"""RelationshipAgent - Agent specialized for relationship advice between two PDN codes.

Extends BasePDNAgent with relationship-specific chat methods:
- chat: Generate relationship advice considering both PDN codes
- _load_relationship_prompt: Compose system prompt from multiple prompt files
- _load_code_data: Load individual PDN code prompt files
"""

import logging
from pathlib import Path
from typing import Dict

from langchain_core.messages import HumanMessage

from .base_pdn_agent import BasePDNAgent, BaseAgentConfig


# Directory containing the relationship agent's own prompts
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Directory containing shared PDN code prompt files
PDN_CODE_DIR = Path(__file__).parent.parent.parent / "pdn_chat_ai" / "binat_agents" / "prompts" / "pdn_code"

# Guardrails prompt path (shared from pdn_chat_ai)
GUARDRAILS_PATH = Path(__file__).parent.parent.parent / "pdn_chat_ai" / "binat_agents" / "prompts" / "guardrails.prompt"

# Hebrew labels for relationship types
RELATIONSHIP_LABELS = {
    "partner": "בן/בת זוג",
    "friend": "חבר/ה",
    "colleague": "עמית/ה לעבודה",
}

# Daily limit message (same as PDNAgent)
DAILY_LIMIT_MESSAGE = "הגעת למגבלת השיחות להיום, אנא חזור אלינו מחר."


class RelationshipAgent(BasePDNAgent):
    """Agent specialized for relationship advice between two PDN codes.

    Provides relationship-specific chat that considers both the user's and
    partner's PDN codes along with the relationship type to generate
    personalized advice in Hebrew.
    """

    def __init__(self, config: BaseAgentConfig = None):
        """Initialize the relationship agent.

        Args:
            config: Agent configuration. Uses defaults if None.
        """
        super().__init__(config)
        self._prompt_cache: Dict[str, str] = {}

    def chat(
        self,
        message: str,
        user_name: str,
        user_code: str,
        partner_code: str,
        relationship_type: str,
        daily_conversation_limit: int = None,
    ) -> str:
        """Generate relationship advice based on both PDN codes.

        Args:
            message: The user's message/question.
            user_name: Display name of the user.
            user_code: User's own PDN code (e.g., "a3").
            partner_code: Partner's PDN code (e.g., "e5").
            relationship_type: One of "partner", "friend", "colleague".
            daily_conversation_limit: Max conversations per day (overrides config).

        Returns:
            Hebrew-language response string, or daily limit message if exceeded.
        """
        # Check daily limit before making LLM call
        if self._has_exceeded_daily_limit(user_name, daily_conversation_limit):
            return DAILY_LIMIT_MESSAGE

        # Compose system prompt from relationship template + both codes + guardrails
        system_prompt = self._load_relationship_prompt(user_code, partner_code, relationship_type)

        # Build user message with context (history, names, codes)
        history_context = self._format_history(user_name)

        # Sanitize user input to prevent prompt injection
        safe_message = self._sanitize_user_input(message)

        if history_context:
            user_message = (
                f"<context>\n"
                f"User: {user_name} | Code: {user_code} | "
                f"Partner code: {partner_code} | "
                f"Relationship: {RELATIONSHIP_LABELS.get(relationship_type, relationship_type)}\n"
                f"Session history:\n{history_context}\n"
                f"</context>\n\n"
                f"<user_message>\n{safe_message}\n</user_message>"
            )
        else:
            user_message = (
                f"<context>\n"
                f"User: {user_name} | Code: {user_code} | "
                f"Partner code: {partner_code} | "
                f"Relationship: {RELATIONSHIP_LABELS.get(relationship_type, relationship_type)}\n"
                f"</context>\n\n"
                f"<user_message>\n{safe_message}\n</user_message>"
            )

        # Invoke LLM with retry logic
        response = self._invoke_llm([
            self._build_system_message(system_prompt),
            HumanMessage(content=user_message),
        ])

        # Track token usage
        self._track_usage(user_name, response)
        response_text = response.content

        # Increment conversation count and add to history after successful response
        if user_name:
            self._increment_conversation_count(user_name)
            self._add_to_history(user_name, message, response_text)

        return response_text

    def _load_relationship_prompt(
        self,
        user_code: str,
        partner_code: str,
        relationship_type: str,
    ) -> str:
        """Compose the system prompt for relationship advice.

        Combines:
        1. relationship_agent.prompt (base relationship instructions)
        2. User's PDN code data (from pdn_code/{user_code}.prompt)
        3. Partner's PDN code data (from pdn_code/{partner_code}.prompt)
        4. guardrails.prompt (safety rules)

        Results are cached keyed by (user_code, partner_code, relationship_type).

        Args:
            user_code: User's PDN code.
            partner_code: Partner's PDN code.
            relationship_type: One of "partner", "friend", "colleague".

        Returns:
            Complete composed system prompt string.

        Raises:
            ValueError: If any prompt file is missing.
        """
        cache_key = f"rel_{user_code}_{partner_code}_{relationship_type}"

        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Load base relationship prompt template
        base_prompt_path = PROMPTS_DIR / "relationship_agent.prompt"
        if not base_prompt_path.exists():
            raise ValueError(
                f"Relationship agent prompt file not found: {base_prompt_path}"
            )
        base_prompt = base_prompt_path.read_text(encoding='utf-8')

        # Load both PDN code descriptions
        user_code_data = self._load_code_data(user_code)
        partner_code_data = self._load_code_data(partner_code)

        # Get relationship type label in Hebrew
        relationship_label = RELATIONSHIP_LABELS.get(relationship_type, relationship_type)

        # Compose final prompt with relationship type context
        # Compose: static instructions first (cacheable), dynamic data last
        # Anthropic caches from the beginning of the prompt, so static content first
        # maximizes cache hit rate across different user/partner code combinations.
        
        # Load guardrails (static — same for all users)
        if not GUARDRAILS_PATH.exists():
            raise ValueError(
                f"Guardrails prompt file not found: {GUARDRAILS_PATH}"
            )
        guardrails = GUARDRAILS_PATH.read_text(encoding='utf-8')

        composed = (
            f"{base_prompt}\n\n"
            f"{guardrails}\n\n"
            f"---\n\n"
            f"## Relationship Context\n"
            f"Relationship type: {relationship_label}\n\n"
            f"## User's PDN Code:\n{user_code_data}\n\n"
            f"## Partner's PDN Code:\n{partner_code_data}\n"
        )

        # Cache the composed prompt
        self._prompt_cache[cache_key] = composed
        return composed

    def _load_code_data(self, pdn_code: str) -> str:
        """Load individual PDN code prompt file from the shared pdn_code/ directory.

        Args:
            pdn_code: The PDN code identifier (e.g., "a3", "e5").

        Returns:
            File content as string.

        Raises:
            ValueError: If the code prompt file does not exist (unknown code).
        """
        if not pdn_code:
            raise ValueError("PDN code is required")

        code_path = PDN_CODE_DIR / f"{pdn_code}.prompt"
        if not code_path.exists():
            raise ValueError(f"Unknown PDN code: {pdn_code}")

        return code_path.read_text(encoding='utf-8')
