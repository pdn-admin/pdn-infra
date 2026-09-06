"""
PDN Calculator Module

This module provides functionality to calculate PDN (Personality Development Number) codes
based on user questionnaire answers. The calculation follows a multi-stage process:

- Stage A: Primary trait calculation (A, T, P, E)
- Stage B: Energy type calculation (D, S, F) 
- Stage C: Validation and tie-breaking for traits
- Stage D: Validation and tie-breaking for energy types
- Stage E: Strengthen dominant trait

The final PDN code is determined by combining the dominant trait and energy type
using a predefined matrix.
"""

import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


def calculate_confidence_score(scores: Dict[str, int]) -> int:
    """
    Calculate a confidence score (0-100) for the PDN code diagnosis.
    Based on how decisive the trait and energy scores are.
    
    Higher score = more confident diagnosis (clear dominant trait/energy).
    Lower score = ambiguous diagnosis (close scores between traits/energies).
    
    Args:
        scores (dict): Dictionary containing all scores (A, T, P, E, D, S, F)
    
    Returns:
        int: Confidence score from 0 to 100
    """
    # Trait confidence (0-50 points)
    trait_scores = sorted([scores.get(k, 0) for k in ['A', 'T', 'P', 'E']], reverse=True)
    total_trait = sum(trait_scores) or 1
    
    # Gap between 1st and 2nd highest as percentage of total
    trait_gap = trait_scores[0] - trait_scores[1] if len(trait_scores) >= 2 else 0
    trait_dominance = (trait_gap / total_trait) * 100
    trait_confidence = min(50, trait_dominance * 2.5)  # Scale to 0-50
    
    # Energy confidence (0-50 points)
    energy_scores = sorted([scores.get(k, 0) for k in ['D', 'S', 'F']], reverse=True)
    total_energy = sum(energy_scores) or 1
    
    energy_gap = energy_scores[0] - energy_scores[1] if len(energy_scores) >= 2 else 0
    energy_dominance = (energy_gap / total_energy) * 100
    energy_confidence = min(50, energy_dominance * 2.5)  # Scale to 0-50
    
    confidence = int(trait_confidence + energy_confidence)
    confidence = max(0, min(100, confidence))
    
    logger.debug("Confidence score: %d (trait: %.1f, energy: %.1f)", confidence, trait_confidence, energy_confidence)
    return confidence


def check_verification_needed(scores: Dict[str, int]) -> bool:
    """
    Check if human verification is needed based on E, P, A, T scores.
    Verification is needed if the gap between the highest and second highest scores is 2 or less.

    Args:
        scores (dict): Dictionary containing the trait scores

    Returns:
        bool: True if verification is needed, False otherwise
    """
    trait_scores = {k: v for k, v in scores.items() if k in ['A', 'T', 'P', 'E']}

    # Get all score values and sort them in descending order
    score_values = sorted(trait_scores.values(), reverse=True)

    # Need at least 2 scores to compare
    if len(score_values) < 2:
        return False

    # Get highest and second highest scores
    highest = score_values[0]
    second_highest = score_values[1]
    gap = highest - second_highest

    logger.debug("Highest score: %s, Second highest: %s, Gap: %s", highest, second_highest, gap)

    if gap <= 2:
        logger.debug("Verification needed: gap of %s points between highest (%s) and second highest (%s)", gap, highest, second_highest)
        return True

    return False


def _resolve_trait_tie(trait_scores: Dict[str, int]) -> str:
    """
    Resolve ties between trait scores deterministically.
    
    When multiple traits have the same highest score, this function flags it
    as a tie rather than silently picking one based on dictionary order.
    The tie is resolved by returning the first tied trait alphabetically,
    but the caller should always check for ties separately.
    
    Args:
        trait_scores: Dictionary of trait -> score (keys: A, T, P, E)
    
    Returns:
        str: The dominant trait letter
    """
    max_score = max(trait_scores.values())
    tied_traits = sorted([k for k, v in trait_scores.items() if v == max_score])
    
    if len(tied_traits) == 1:
        return tied_traits[0]
    
    # When tied, return first alphabetically but log the tie
    # The tie will be detected by check_verification_needed (gap=0)
    logger.info("Trait tie detected: %s all have score %d", tied_traits, max_score)
    return tied_traits[0]


def _resolve_energy_tie(energy_scores: Dict[str, int]) -> str:
    """
    Resolve ties between energy scores deterministically.
    
    Args:
        energy_scores: Dictionary of energy -> score (keys: D, S, F)
    
    Returns:
        str: The dominant energy letter
    """
    max_score = max(energy_scores.values())
    tied_energies = sorted([k for k, v in energy_scores.items() if v == max_score])
    
    if len(tied_energies) == 1:
        return tied_energies[0]
    
    logger.info("Energy tie detected: %s all have score %d", tied_energies, max_score)
    return tied_energies[0]


def calculate_pdn_code(answers: Dict[str, Any], return_details: bool = False, user_id: str = None) -> str:
    """
    Calculate the PDN code based on user's answers.
    
    Args:
        answers (dict): Dictionary containing user's answers with question numbers as keys
        return_details (bool): If True, returns detailed calculation steps along with the PDN code
        user_id (str): Optional user identifier for log messages
        
    Returns:
        str or dict: The calculated PDN code (e.g., 'A7', 'P10', 'T4', etc.) or dict with details if return_details=True
    """
    # Initialize result dictionary with proper typing
    result: Dict[str, Any] = {
        'pdn_code': 'NA',
        'trait': 'Undetermined',
        'energy': 'Undetermined',
        'scores': {'A': 0, 'T': 0, 'P': 0, 'E': 0, 'D': 0, 'S': 0, 'F': 0},
        'needs_verification': False
    }
    
    # Initialize calculation details if requested
    calculation_details = [] if return_details else None

    # Stage A: Primary Trait Calculation
    for i in range(1, 27):
        if str(i) in answers:
            answer = answers[str(i)]['selected_option_code']
            if answer == 'AP':
                result['scores']['A'] += 1
                result['scores']['P'] += 1
            elif answer == 'ET':
                result['scores']['E'] += 1
                result['scores']['T'] += 1
            elif answer == 'AE':
                result['scores']['A'] += 1
                result['scores']['E'] += 1
            elif answer == 'TP':
                result['scores']['T'] += 1
                result['scores']['P'] += 1
    # Find dominant trait, but only if there are actual scores > 0
    trait_scores = {k: v for k, v in result['scores'].items() if k in ['A', 'T', 'P', 'E']}
    if any(score > 0 for score in trait_scores.values()):
        dominant_trait: str = _resolve_trait_tie(trait_scores)
    else:
        dominant_trait: str = 'Undetermined'
    result['trait'] = dominant_trait

    logger.debug("Stage A: Trait Calculation for A %s", result['scores']['A'])
    logger.debug("Stage A: Trait Calculation for T %s", result['scores']['T'])
    logger.debug("Stage A: Trait Calculation for P %s", result['scores']['P'])
    logger.debug("Stage A: Trait Calculation for E %s", result['scores']['E'])
    logger.debug("Stage A dominant trait %s", dominant_trait)
    
    
    # Add to calculation details if requested
    if calculation_details is not None:
        calculation_details.append({
            'stage': 'A',
            'name': 'Primary Trait Calculation',
            'scores': {
                'A': result['scores']['A'],
                'T': result['scores']['T'],
                'P': result['scores']['P'],
                'E': result['scores']['E']
            },
            'dominant': dominant_trait
        })

    # Stage B: Energy Type Calculation
    energy_counts: Dict[str, int] = {'D': 0, 'S': 0, 'F': 0}
    for i in range(27, 38):
        if str(i) in answers:
            answer_data = answers[str(i)]
            if 'ranking' not in answer_data:
                logger.warning("Question %d has no 'ranking' key, skipping.", i)
                continue
            ranking = answer_data['ranking']
            for energy, rank in ranking.items():
                if rank == 1:
                    energy_counts[energy] += 3
                elif rank == 2:
                    energy_counts[energy] += 2
                elif rank == 3:
                    energy_counts[energy] += 1

    result['scores'].update(energy_counts)
    # Find dominant energy, but only if there are actual scores > 0
    if any(score > 0 for score in energy_counts.values()):
        dominant_energy = _resolve_energy_tie(energy_counts)
    else:
        dominant_energy = 'Undetermined'
    result['energy'] = dominant_energy

    logger.debug("Stage B: Energy Type Calculation for D %s", energy_counts['D'])
    logger.debug("Stage B: Energy Type Calculation for S %s", energy_counts['S'])
    logger.debug("Stage B: Energy Type Calculation for F %s", energy_counts['F'])
    logger.debug("Stage B dominant energy %s", dominant_energy)
    
    
    # Add to calculation details if requested
    if calculation_details is not None:
        calculation_details.append({
            'stage': 'B',
            'name': 'Energy Type Calculation',
            'scores': {
                'D': energy_counts['D'],
                'S': energy_counts['S'],
                'F': energy_counts['F']
            },
            'dominant': dominant_energy
        })

    # Stage C: Validation and Tie-Breaking
    for i in range(38, 43):
        if str(i) in answers:
            answer_data = answers[str(i)]
            if 'ranking' not in answer_data:
                logger.warning("Question %d has no 'ranking' key, skipping.", i)
                continue
            ranking = answer_data['ranking']
            traits = list(ranking.keys())
            if len(traits) < 2:
                continue
            trait1, trait2 = traits
            value1, value2 = ranking[trait1], ranking[trait2]

            difference = value1 - value2
            score_adjustment = abs(difference)

            if difference > 0:
                result['scores'][trait1] += 1
                # result['scores'][trait2] -= 1
            elif difference < 0:
                # result['scores'][trait1] -= 1
                result['scores'][trait2] += 1

    # Find dominant trait, but only if there are actual scores > 0
    trait_scores = {k: v for k, v in result['scores'].items() if k in ['A', 'T', 'P', 'E']}
    if any(score > 0 for score in trait_scores.values()):
        dominant_trait = _resolve_trait_tie(trait_scores)
    else:
        dominant_trait = 'Undetermined'
    result['trait'] = dominant_trait

    logger.debug("Stage C: Trait Calculation for A %s", result['scores']['A'])
    logger.debug("Stage C: Trait Calculation for T %s", result['scores']['T'])
    logger.debug("Stage C: Trait Calculation for P %s", result['scores']['P'])
    logger.debug("Stage C: Trait Calculation for E %s", result['scores']['E'])
    logger.debug("Stage C dominant trait %s", dominant_trait)
    
    
    # Add to calculation details if requested
    if calculation_details is not None:
        calculation_details.append({
            'stage': 'C',
            'name': 'Validation and Tie-Breaking (Traits)',
            'scores': {
                'A': result['scores']['A'],
                'T': result['scores']['T'],
                'P': result['scores']['P'],
                'E': result['scores']['E']
            },
            'dominant': dominant_trait
        })

    # Stage D: Validation and Tie-Breaking
    for i in range(43, 57):
        if str(i) in answers:
            answer_data = answers[str(i)]
            if 'ranking' not in answer_data:
                logger.warning("Question %d has no 'ranking' key, skipping.", i)
                continue
            ranking = answer_data['ranking']
            # Get the trait combinations and their rankings
            trait_combinations = list(ranking.keys())
            if len(trait_combinations) == 2:
                combo1, combo2 = trait_combinations
                value1, value2 = ranking[combo1], ranking[combo2]

                difference = value1 - value2
                score_adjustment = abs(difference) * 2

                if difference > 0:
                    # Add points to both traits in the winning combination
                    result['scores'][combo1[0]] += 1
                    result['scores'][combo1[1]] += 1
                    # Subtract points from both traits in the losing combination
                    # result['scores'][combo2[0]] -= 1
                    # result['scores'][combo2[1]] -= 1
                elif difference < 0:
                    # Add points to both traits in the winning combination
                    result['scores'][combo2[0]] += 1
                    result['scores'][combo2[1]] += 1
                    # Subtract points from both traits in the losing combination
                    # result['scores'][combo1[0]] -= 1
                    # result['scores'][combo1[1]] -= 1

    # Recalculate dominant trait after all adjustments
    trait_scores = {k: v for k, v in result['scores'].items() if k in ['A', 'T', 'P', 'E']}
    if any(score > 0 for score in trait_scores.values()):
        dominant_trait = _resolve_trait_tie(trait_scores)
    else:
        dominant_trait = 'Undetermined'
    result['trait'] = dominant_trait

    logger.debug("Stage D: Trait Calculation for A %s", result['scores']['A'])
    logger.debug("Stage D: Trait Calculation for T %s", result['scores']['T'])
    logger.debug("Stage D: Trait Calculation for P %s", result['scores']['P'])
    logger.debug("Stage D: Trait Calculation for E %s", result['scores']['E'])
    logger.debug("Stage D dominant trait %s", dominant_trait)
    
    
    # Add to calculation details if requested
    if calculation_details is not None:
        calculation_details.append({
            'stage': 'D',
            'name': 'Validation and Tie-Breaking (Energy Types)',
            'scores': {
                'A': result['scores']['A'],
                'T': result['scores']['T'],
                'P': result['scores']['P'],
                'E': result['scores']['E'],
                'D': result['scores']['D'],
                'S': result['scores']['S'],
                'F': result['scores']['F']
            },
            'dominant': dominant_trait
        })

    # Stage E: Strengthen Dominant Trait
    # Save dominant trait BEFORE Stage E for comparison
    dominant_before_stage_e = dominant_trait

    # Track whether Stage E was actually answered
    stage_e_answered = any(
        str(i) in answers and 'ranking' in answers[str(i)]
        for i in range(57, 62)
    )
    stage_e_answer_count = sum(
        1 for i in range(57, 62)
        if str(i) in answers and 'ranking' in answers[str(i)]
    )
    
    if not stage_e_answered:
        logger.warning("[%s] Stage E (questions 57-60) has NO answers - result based on stages A-D only", user_id or '?')

    for i in range(57, 62):
        if str(i) in answers:
            answer_data = answers[str(i)]
            if 'ranking' not in answer_data:
                logger.warning("Question %d has no 'ranking' key, skipping. Data: %s", i, list(answer_data.keys()))
                continue
            ranking = answer_data['ranking']
            for trait, rank in ranking.items():
                if rank == 1:
                    result['scores'][trait] += 8
                elif rank == 2:
                    result['scores'][trait] += 4
                elif rank == 3:
                    result['scores'][trait] += 2
                elif rank == 4:
                    result['scores'][trait] += 0

    # Find dominant trait, but only if there are actual scores > 0
    trait_scores = {k: v for k, v in result['scores'].items() if k in ['A', 'T', 'P', 'E']}
    if any(score > 0 for score in trait_scores.values()):
        dominant_trait = _resolve_trait_tie(trait_scores)
    else:
        dominant_trait = 'Undetermined'
    result['trait'] = dominant_trait

    # Check if Stage E flipped the dominant trait (override detection)
    stage_e_override = False
    if dominant_before_stage_e != 'Undetermined' and dominant_trait != dominant_before_stage_e:
        stage_e_override = True
        logger.warning("[%s] Stage E override: dominant trait changed from %s to %s", user_id or '?', dominant_before_stage_e, dominant_trait)
    result['stage_e_override'] = stage_e_override
    result['missing_stage_e'] = not stage_e_answered
    result['stage_e_answer_count'] = stage_e_answer_count

    logger.debug("Stage E: Trait Calculation for A %s", result['scores']['A'])
    logger.debug("Stage E: Trait Calculation for T %s", result['scores']['T'])
    logger.debug("Stage E: Trait Calculation for P %s", result['scores']['P'])
    logger.debug("Stage E: Trait Calculation for E %s", result['scores']['E'])
    logger.debug("Stage E dominant trait %s", dominant_trait)
    
    # Add to calculation details if requested
    if calculation_details is not None:
        calculation_details.append({
            'stage': 'E',
            'name': 'Strengthen Dominant Trait',
            'scores': {
                'A': result['scores']['A'],
                'T': result['scores']['T'],
                'P': result['scores']['P'],
                'E': result['scores']['E'],
                'D': result['scores']['D'],
                'S': result['scores']['S'],
                'F': result['scores']['F']
            },
            'dominant': dominant_trait,
            'stage_e_override': stage_e_override,
            'dominant_before_stage_e': dominant_before_stage_e,
            'missing_stage_e': not stage_e_answered,
            'stage_e_answer_count': stage_e_answer_count
        })

    # Check if verification is needed based on E, P, A, T scores
    result['needs_verification'] = check_verification_needed(result['scores'])
    
    # Also flag for verification if Stage E is missing (incomplete questionnaire)
    if not stage_e_answered:
        result['needs_verification'] = True
        logger.warning("[%s] Flagging for verification: Stage E (self-scoring) was not answered", user_id or '?')
    
    if result['needs_verification']:
        logger.warning("[%s] PDN calculation requires human verification due to close scores", user_id or '?')
    
    # Calculate confidence score
    confidence_score = calculate_confidence_score(result['scores'])
    result['confidence_score'] = confidence_score
    
    # Finalizing the PDN code
    pdn_matrix: Dict[Tuple[str, str], str] = {
        ('P', 'D'): 'P10', ('P', 'S'): 'P2', ('P', 'F'): 'P6',
        ('E', 'D'): 'E1', ('E', 'S'): 'E5', ('E', 'F'): 'E9',
        ('A', 'D'): 'A7', ('A', 'S'): 'A11', ('A', 'F'): 'A3',
        ('T', 'D'): 'T4', ('T', 'S'): 'T8', ('T', 'F'): 'T12'
    }

    pdn_code: str = pdn_matrix.get((result['trait'], result['energy']), 'NA')
    result['pdn_code'] = pdn_code

    logger.debug("Finalizing the PDN code %s", pdn_code)
    
    # Add final result to calculation details if requested
    if calculation_details is not None:
        calculation_details.append({
            'stage': 'Final',
            'name': 'Final Result',
            'pdn_code': pdn_code,
            'trait': result['trait'],
            'energy': result['energy'],
            'scores': result['scores'].copy(),
            'needs_verification': result['needs_verification'],
            'stage_e_override': result.get('stage_e_override', False),
            'dominant_before_stage_e': dominant_before_stage_e if stage_e_override else None,
            'confidence_score': confidence_score,
            'missing_stage_e': not stage_e_answered,
            'stage_e_answer_count': stage_e_answer_count
        })
        return {
            'pdn_code': pdn_code,
            'needs_verification': result['needs_verification'],
            'stage_e_override': result.get('stage_e_override', False),
            'missing_stage_e': not stage_e_answered,
            'calculation_details': calculation_details
        }

    # If stage E overrode the dominant trait, flag it for review
    if result.get('stage_e_override'):
        return {
            'pdn_code': pdn_code,
            'needs_verification': result['needs_verification'],
            'stage_e_override': True,
            'missing_stage_e': not stage_e_answered,
            'dominant_before_stage_e': dominant_before_stage_e,
            'scores': result['scores'],
            'confidence_score': confidence_score
        }

    # If verification is needed, return the full result object instead of just the code
    if result['needs_verification']:
        return {
            'pdn_code': pdn_code,
            'needs_verification': True,
            'missing_stage_e': not stage_e_answered,
            'scores': result['scores'],
            'confidence_score': confidence_score
        }
    
    return pdn_code
