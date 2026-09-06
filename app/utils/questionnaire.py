"""
Questionnaire Module

This module provides functionality for managing the PDN (Personality Development Number)
questionnaire system. It handles question retrieval, phase management, and question
type classification for the multi-stage personality assessment.

Key features:
- Question retrieval by number and phase
- Phase classification (Part A through Part F)
- Question type and instruction management
- Structured question data formatting
"""

import json
import logging

logger = logging.getLogger(__name__)


def get_question(question_number: int, questions: dict):
    """
    Fetch a specific question by its number from the questionnaire data.
    
    Args:
        question_number (int): The question number to retrieve
        questions (dict): The complete questions data structure
        
    Returns:
        dict: Dictionary containing question data with keys:
            - question_number: The question number
            - question: The question text
            - options: Available answer options
            - stage: The phase/part (PartA, PartB, etc.)
            - type: Question type (if specified)
            - instructions: Phase-specific instructions
        Returns {"message": "No more questions."} if question not found
    """

    # Check Part A questions (1-26)
    if 1 <= question_number <= 26:
        logger.debug("Part A")
        phase = "PartA"
    # Check Part B questions (27-37)
    elif 27 <= question_number <= 37:
        logger.debug("Part B")
        phase = "PartB"
    # Check Part C questions (38-42)
    elif 38 <= question_number <= 42:
        logger.debug("Part C")
        phase = "PartC"
    # Check Part D questions (43-56)
    elif 43 <= question_number <= 56:
        phase = "PartD"
    # Check Part E questions (57-61)    
    elif 57 <= question_number <= 61:
        phase = "PartE"
    # Check Part F questions (62-67)
    elif 62 <= question_number <= 67:
        phase = "PartF"
    else:
        return {"message": "No more questions."}

    # Get the question from the appropriate phase
    question = questions["phases"][phase]["questions"].get(str(question_number))

    if not question:
        return {"message": "No more questions."}

    return {
        "question_number": question_number,
        "question": question["text"],
        "options": question["options"],
        "stage": phase,
        "type": question.get("type"),
        "instructions": questions["phases"][phase].get("instructions", "")
    }
