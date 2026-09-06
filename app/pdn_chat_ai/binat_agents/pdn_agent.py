"""PDNAgent - Single agent for all PDN chat interactions."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from langchain_core.messages import HumanMessage

from app.pdn_relationships.agents.base_pdn_agent import BasePDNAgent, BaseAgentConfig, UserHistory
from config import Config


class PDNAgent(BasePDNAgent):
    """Single agent for all PDN chat interactions.

    Extends BasePDNAgent with PDN-specific chat methods:
    - chat_with_binat: General PDN chat
    - build_21_transformation_plan: 21-day plan generation
    - daily_training: Daily training responses
    - _load_prompt: PDN code prompt loading with caching
    """

    def __init__(self, llm_provider=None, model_name=None):
        """Initialize the PDN agent.

        Args:
            llm_provider (str, optional): LLM provider ('openai' or 'anthropic').
                                        Defaults to config value.
            model_name (str, optional): Model name to use. Defaults to config value.
        """
        agent_config = BaseAgentConfig(
            llm_provider=llm_provider,
            model_name=model_name,
        )
        super().__init__(config=agent_config)

        self._prompt_cache = {}
        self._prompts_dir = Path(__file__).parent / "prompts"

    @staticmethod
    def _clean_response(text) -> str:
        """Strip internal prompt markers and emojis from LLM responses."""
        import re
        if isinstance(text, list):
            parts = []
            for block in text:
                if hasattr(block, 'text'):
                    parts.append(block.text)
                elif isinstance(block, str):
                    parts.append(block)
            text = ''.join(parts)
        if not isinstance(text, str):
            text = str(text) if text is not None else ''
        # Remove [STOP — wait for user response] and similar bracketed instructions
        text = re.sub(r'\[STOP[^\]]*\]', '', text)
        # Remove all emoji / pictographic characters
        text = re.sub(
            r'[\U00010000-\U0010FFFF'   # supplementary planes (most emoji)
            r'\U00002600-\U000027BF'    # misc symbols, dingbats
            r'\U0001F300-\U0001FAFF'   # emoji blocks
            r'\u2600-\u27BF'           # BMP symbols
            r'\uFE00-\uFE0F'           # variation selectors
            r'\u200D'                  # zero-width joiner
            r']+',
            '', text, flags=re.UNICODE
        )
        result = text.strip()
        if not result:
            import logging
            logging.getLogger(__name__).warning(
                "_clean_response: output is empty after cleaning (input type=%s, input preview=%r)",
                type(text).__name__, str(text)[:100]
            )
        return result

    def _load_prompt(self, pdn_code: str, prompt_file: str) -> str:
        """Load prompt file with caching. Raises FileNotFoundError with clear message if code is invalid."""
        if not pdn_code:
            raise ValueError("PDN code is required")

        code_path = self._prompts_dir / "pdn_code" / f"{pdn_code}.prompt"
        if not code_path.exists():
            raise ValueError(f"Unknown PDN code: {pdn_code}")

        cache_key = f"{pdn_code}_{prompt_file}"
        if cache_key not in self._prompt_cache:
            prompt_content = (
                (self._prompts_dir / prompt_file).read_text(encoding='utf-8') +
                code_path.read_text(encoding='utf-8')
            )
            if prompt_file in ["binat_agent.prompt", "daily_training.prompt"]:
                prompt_content += (self._prompts_dir / "guardrails.prompt").read_text(encoding='utf-8')
            self._prompt_cache[cache_key] = prompt_content
        return self._prompt_cache[cache_key]

    def get_usage_stats(self, days: int = 14) -> Dict[str, Any]:
        """Return token usage stats with daily history, cost projections, and model recommendations."""

        # Pricing per million tokens by model family
        MODEL_PRICING = {
            'sonnet': {
                'input': 3.0, 'output': 15.0,
                'cache_write': 3.75, 'cache_read': 0.30,
            },
            'haiku': {
                'input': 0.80, 'output': 4.0,
                'cache_write': 1.0, 'cache_read': 0.08,
            },
            'gpt-4o-mini': {
                'input': 0.15, 'output': 0.60,
                'cache_write': 0.15, 'cache_read': 0.075,
            },
        }

        def _get_pricing(model_name: str) -> dict:
            """Determine pricing tier from model name."""
            model_lower = (model_name or '').lower()
            if 'haiku' in model_lower:
                return MODEL_PRICING['haiku']
            elif 'gpt-4o-mini' in model_lower:
                return MODEL_PRICING['gpt-4o-mini']
            else:
                # Default to Sonnet pricing (claude-sonnet-*, claude-3-*)
                return MODEL_PRICING['sonnet']

        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        def calc_cost(d, pricing=None):
            if pricing is None:
                pricing = _get_pricing(d.get('model', ''))
            uncached = d['input_tokens'] - d.get('cache_creation_tokens', 0) - d.get('cache_read_tokens', 0)
            return (
                (max(0, uncached) / 1e6) * pricing['input'] +
                (d['output_tokens'] / 1e6) * pricing['output'] +
                (d.get('cache_creation_tokens', 0) / 1e6) * pricing['cache_write'] +
                (d.get('cache_read_tokens', 0) / 1e6) * pricing['cache_read']
            )

        def calc_savings(d, pricing=None):
            if pricing is None:
                pricing = _get_pricing(d.get('model', ''))
            cache_read = d.get('cache_read_tokens', 0)
            if cache_read <= 0:
                return 0
            return (cache_read / 1e6) * (pricing['input'] - pricing['cache_read'])

        def calc_cost_with_model(d, target_model: str):
            """Calculate what the cost WOULD BE with a different model."""
            pricing = MODEL_PRICING.get(target_model, MODEL_PRICING['sonnet'])
            return calc_cost(d, pricing)

        # Build per-user summary + daily breakdown
        users = {}
        daily_totals = {}

        for user, date_data in self.token_usage.items():
            user_total = {'input_tokens': 0, 'output_tokens': 0, 'cache_creation_tokens': 0,
                          'cache_read_tokens': 0, 'calls': 0, 'model': '', 'daily': {}}

            for date_str, d in sorted(date_data.items()):
                if date_str < cutoff:
                    continue
                user_total['input_tokens'] += d['input_tokens']
                user_total['output_tokens'] += d['output_tokens']
                user_total['cache_creation_tokens'] += d.get('cache_creation_tokens', 0)
                user_total['cache_read_tokens'] += d.get('cache_read_tokens', 0)
                user_total['calls'] += d['calls']
                user_total['model'] = d.get('model', '')
                user_total['daily'][date_str] = {**d, 'cost': round(calc_cost(d), 4)}

                if date_str not in daily_totals:
                    daily_totals[date_str] = {'input_tokens': 0, 'output_tokens': 0,
                                              'cache_creation_tokens': 0, 'cache_read_tokens': 0,
                                              'calls': 0, 'cost': 0}
                dt = daily_totals[date_str]
                dt['input_tokens'] += d['input_tokens']
                dt['output_tokens'] += d['output_tokens']
                dt['cache_creation_tokens'] += d.get('cache_creation_tokens', 0)
                dt['cache_read_tokens'] += d.get('cache_read_tokens', 0)
                dt['calls'] += d['calls']
                dt['cost'] += calc_cost(d)

            user_total['total_cost'] = round(calc_cost(user_total), 4)
            user_total['cache_savings'] = round(calc_savings(user_total), 4)
            users[user] = user_total

        # Round daily totals
        for dt in daily_totals.values():
            dt['cost'] = round(dt['cost'], 4)

        # Projection: average daily cost over active days → project to 30 days
        sorted_days = sorted(daily_totals.keys())
        active_days = len(sorted_days)
        total_cost_period = sum(dt['cost'] for dt in daily_totals.values())
        avg_daily_cost = total_cost_period / active_days if active_days > 0 else 0

        # Calculate total tokens for "what-if" model comparison
        total_input = sum(u['input_tokens'] for u in users.values())
        total_output = sum(u['output_tokens'] for u in users.values())
        total_cache_creation = sum(u['cache_creation_tokens'] for u in users.values())
        total_cache_read = sum(u['cache_read_tokens'] for u in users.values())
        total_calls = sum(u['calls'] for u in users.values())

        aggregate = {
            'input_tokens': total_input,
            'output_tokens': total_output,
            'cache_creation_tokens': total_cache_creation,
            'cache_read_tokens': total_cache_read,
            'model': '',
        }

        # Model comparison: what would the same usage cost on different models?
        model_comparison = {
            'sonnet': {
                'cost': round(calc_cost_with_model(aggregate, 'sonnet'), 4),
                'per_call': round(calc_cost_with_model(aggregate, 'sonnet') / max(total_calls, 1), 4),
                'label': 'Claude Sonnet 5 (נוכחי)',
            },
            'haiku': {
                'cost': round(calc_cost_with_model(aggregate, 'haiku'), 4),
                'per_call': round(calc_cost_with_model(aggregate, 'haiku') / max(total_calls, 1), 4),
                'label': 'Claude 3.5 Haiku (מומלץ)',
                'savings_pct': round((1 - calc_cost_with_model(aggregate, 'haiku') / max(calc_cost_with_model(aggregate, 'sonnet'), 0.001)) * 100, 1),
            },
        }

        projection = {
            'active_days': active_days,
            'avg_daily_cost': round(avg_daily_cost, 4),
            'projected_monthly': round(avg_daily_cost * 30, 2),
            'projected_yearly': round(avg_daily_cost * 365, 2),
            'per_conversation_avg': round(total_cost_period / max(total_calls / 8, 1), 4),  # ~8 turns per conversation
            'per_100_conversations': round((total_cost_period / max(total_calls / 8, 1)) * 100, 2),
        }

        # Recommendation
        recommendation = None
        if total_cost_period > 0 and model_comparison['haiku']['savings_pct'] > 50:
            recommendation = {
                'action': 'switch_to_haiku',
                'label': 'מומלץ: מעבר ל-Claude 3.5 Haiku',
                'reason': f"חיסכון של {model_comparison['haiku']['savings_pct']}% בעלויות עם שמירה על איכות טובה בעברית",
                'current_cost_100': projection['per_100_conversations'],
                'projected_cost_100': round(model_comparison['haiku']['per_call'] * 800, 2),  # 100 conv × 8 turns
            }

        return {
            'users': users,
            'daily_totals': dict(sorted(daily_totals.items())),
            'projection': projection,
            'model_comparison': model_comparison,
            'recommendation': recommendation,
            'period_days': days,
        }

    def chat_with_binat(self, user_query: str, user_name: str = None, pdn_code: str = None, daily_conversation_limit: int = None) -> str:
        """Generate response using PDN prompt."""
        if self._has_exceeded_daily_limit(user_name, daily_conversation_limit):
            return "הגעת למגבלת השיחות להיום, אנא חזור אלינו מחר."

        system_prompt = self._load_prompt(pdn_code, "binat_agent.prompt")
        history_context = self._format_history(user_name)

        # Sanitize user input to prevent prompt injection
        safe_query = self._sanitize_user_input(user_query)

        if history_context:
            user_message = (
                f"<context>\n"
                f"User: {user_name} | Code: {pdn_code}\n"
                f"Session history:\n{history_context}\n"
                f"</context>\n\n"
                f"<user_message>\n{safe_query}\n</user_message>"
            )
        else:
            user_message = (
                f"<context>\n"
                f"User: {user_name} | Code: {pdn_code}\n"
                f"</context>\n\n"
                f"<user_message>\n{safe_query}\n</user_message>"
            )

        response = self._invoke_llm([
            self._build_system_message(system_prompt),
            HumanMessage(content=user_message)
        ])
        self._track_usage(user_name, response)
        response_text = self._clean_response(response.content)

        # Increment count AFTER successful LLM call
        if user_name:
            self._increment_conversation_count(user_name)
            self._add_to_history(user_name, user_query, response_text)

        return response_text

    def build_21_transformation_plan(self, user_goal: str, user_name: str, pdn_code: str, daily_conversation_limit: int = None) -> str:
        """Generate 21-day transformation plan."""
        if self._has_exceeded_daily_limit(user_name, daily_conversation_limit):
            return "הגעת למגבלת השיחות להיום, אנא חזור אלינו מחר."

        system_prompt = self._load_prompt(pdn_code, "21_plan.prompt")
        safe_goal = self._sanitize_user_input(user_goal)
        user_message = f"user_name: {user_name}\nuser_pdn_code: {pdn_code}\nuser_goal: {safe_goal}"

        response = self._invoke_llm([
            self._build_system_message(system_prompt),
            HumanMessage(content=user_message)
        ], max_tokens=4000)
        self._track_usage(user_name, response)
        response_text = self._clean_response(response.content)

        # If empty, return a friendly error
        if not response_text.strip():
            self.logger.error("Plan generation returned empty for %s", user_name)
            return (
                "<div style='font-family:Arial,sans-serif;direction:rtl;padding:20px;color:#1a2540;'>"
                "<p style='font-size:1rem;font-weight:600;'>מצטערים, לא הצלחנו לבנות את התוכנית כרגע.</p>"
                "<p style='font-size:0.9rem;color:#7a7060;'>נסה שוב בעוד כמה דקות, או פנה לתמיכה אם הבעיה נמשכת.</p>"
                "</div>"
            )

        # Increment count AFTER successful LLM call
        if user_name:
            self._increment_conversation_count(user_name)
            self._add_to_history(user_name, user_goal, response_text)

        return response_text

    def daily_training(self, user_name: str, pdn_code: str, day_task: str, daily_conversation_limit: int = None) -> str:
        """Generate personalized daily training response."""
        if self._has_exceeded_daily_limit(user_name, daily_conversation_limit):
            return "הגעת למגבלת השיחות להיום, אנא חזור אלינו מחר."

        system_prompt = self._load_prompt(pdn_code, "daily_training.prompt")
        safe_task = self._sanitize_user_input(day_task)
        user_message = f"User name: {user_name}\n User day Task: {safe_task}\n."

        response = self._invoke_llm([
            self._build_system_message(system_prompt),
            HumanMessage(content=user_message)
        ])
        self._track_usage(user_name, response)
        response_text = self._clean_response(response.content)

        # Increment count AFTER successful LLM call
        if user_name:
            self._increment_conversation_count(user_name)
            self._add_to_history(user_name, day_task, response_text)

        return response_text
