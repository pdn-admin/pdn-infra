"""
NeoAgent - AI agent for Neo P.D.N Center interactions.
Handles company analysis and voice processing for insurance products.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if OpenAI API key is set in environment
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. "
        "Please set it before running the application."
    )


class NeoAgent:
    """
    AI Agent for Neo P.D.N Center
    Processes company data and provides intelligent analysis of insurance products.
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.7):
        """
        Initialize the Neo Agent.
        
        Args:
            model_name: The OpenAI model to use (default: gpt-4)
            temperature: Controls randomness in responses (default: 0.7)
        """
        self.model_name = model_name
        self.temperature = temperature
        
        self.langsmith_client = None
        
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=800,  # Limit response length for faster completion
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Load system prompt
        self.system_prompt = self._load_system_prompt()
        
        logger.info(f"NeoAgent initialized with model: {model_name} and LangSmith tracing enabled")
    
    def _load_system_prompt(self) -> str:
        """
        Load the system prompt for Neo agent.
        
        Returns:
            The system prompt as a string
            
        Raises:
            FileNotFoundError: If the prompt file does not exist
        """
        prompt_file = Path(__file__).parent / 'prompts' / 'neo_system.prompt'
        
        if not prompt_file.exists():
            raise FileNotFoundError(f"System prompt file not found: {prompt_file}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    
    def analyze_customer_code(self, transcribed_text: str, company_data: Optional[Dict] = None) -> str:
        """
        Analyze customer communication from voice recording and provide PDN insights.
        
        Args:
            transcribed_text: The transcribed text from the voice recording
            company_data: Optional company context (name, about, products, url)
            
        Returns:
            str: PDN code analysis and customer interaction recommendations in Hebrew
        """
        # Validate input
        if not transcribed_text or not transcribed_text.strip():
            raise ValueError("Transcribed text cannot be empty")
        
        if len(transcribed_text.strip()) < 10:
            raise ValueError("Transcribed text too short for meaningful analysis (minimum 10 characters)")
        
        try:
            logger.info(f"Analyzing customer code for {len(transcribed_text)} character transcription")
            logger.debug(f"Transcription preview: {transcribed_text[:100]}...")
            
            
            
            prompt = ChatPromptTemplate.from_messages([
                SystemMessagePromptTemplate.from_template(self.system_prompt),
                HumanMessagePromptTemplate.from_template(
                    """בהתבסס על ההקלטה הקולית הבאה של הלקוח, ספק אנליזה מקצועית:

תמלול ההקלטה:
{transcribed_text}

אנא ספק אנליזה המכילה:
1. **קוד  ** - זהה את הקוד הדומיננטי (A/T/P/E)
2. **ניתוח סגנון תקשורת** - איך הלקוח מתבטא ומתקשר
3. **צרכים מרכזיים** - מה חשוב ללקוח בהתבסס על דבריו
4. **המלצות לאינטראקציה** - כיצד לגשת ולתקשר עם הלקוח בצורה אופטימלית

התשובה בעברית, תמציתית, מקצועית וממוקדת."""
                )
            ])

            messages = prompt.format_messages(
                transcribed_text=transcribed_text
            )
            
            # Time the LLM invoke call
            start_time = time.time()
            logger.info(f"Starting LLM invoke for customer code analysis...")
            
            response = self.llm.invoke(messages)
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            logger.info(f"LLM invoke completed in {elapsed_time:.2f} seconds")
            logger.info(f"Customer analysis completed successfully: {len(response.content)} characters")
            logger.info(f"Tokens per second estimate: {len(response.content) / elapsed_time:.2f}")
            
            return response.content
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error analyzing customer code: {str(e)}")
            raise
    
# Singleton instance
_neo_agent_instance: Optional[NeoAgent] = None


def get_neo_agent() -> NeoAgent:
    """
    Get or create the singleton NeoAgent instance.
    
    Returns:
        The NeoAgent instance
    """
    global _neo_agent_instance
    
    if _neo_agent_instance is None:
        _neo_agent_instance = NeoAgent()
    
    return _neo_agent_instance

