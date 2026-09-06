"""
Test concurrent answer submission to verify race condition fix
"""
import json
import threading
import time
import os
from pathlib import Path

# Standalone implementation for testing
class PDNFilePath:
    def __init__(self):
        self.base_dir = Path('saved_results')
    
    def get_user_dir(self, user_email):
        safe_username = "".join(c for c in user_email if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_username = safe_username.replace(' ', '_')
        user_dir = self.base_dir / safe_username
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def get_user_file_path(self, user_email, filename):
        user_dir = self.get_user_dir(user_email)
        return user_dir / filename

def save_answer(email, question_number, answer_data, question_text=None):
    """Standalone save_answer implementation for testing"""
    import fcntl
    
    pdn_file_path = PDNFilePath()
    filename = f"{email}_answers.json"
    file_path = pdn_file_path.get_user_file_path(email, filename)
    lock_path = file_path.with_suffix('.lock')
    
    # Acquire lock
    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        
        try:
            data = {}
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    data = {}
            
            filtered_answer_data = {k: v for k, v in answer_data.items() if v is not None}
            if question_text:
                filtered_answer_data['question_text'] = question_text
            
            data[str(question_number)] = filtered_answer_data
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def test_concurrent_answer_submission():
    """Test that concurrent answer submissions don't lose data"""
    test_email = "test_concurrent@example.com"
    num_questions = 65
    num_threads = 5
    
    pdn_file_path = PDNFilePath()
    filename = f"{test_email}_answers.json"
    file_path = pdn_file_path.get_user_file_path(test_email, filename)
    if file_path.exists():
        file_path.unlink()
    
    def submit_answers(thread_id, start_q, end_q):
        for q_num in range(start_q, end_q):
            answer_data = {
                'selected_option_code': f'T{thread_id}_Q{q_num}',
                'ranking': None,
                'question_options': ['opt1', 'opt2']
            }
            save_answer(test_email, q_num, answer_data, f"Question {q_num}")
            time.sleep(0.01)
    
    threads = []
    questions_per_thread = num_questions // num_threads
    
    for i in range(num_threads):
        start = i * questions_per_thread + 1
        end = start + questions_per_thread
        t = threading.Thread(target=submit_answers, args=(i, start, end))
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    expected_questions = set(str(i) for i in range(1, num_questions + 1))
    actual_questions = set(saved_data.keys()) - {'metadata'}
    
    assert actual_questions == expected_questions, \
        f"Missing: {expected_questions - actual_questions}, Extra: {actual_questions - expected_questions}"
    
    for q_num in range(1, num_questions + 1):
        assert str(q_num) in saved_data, f"Question {q_num} not saved"
        assert 'selected_option_code' in saved_data[str(q_num)]
        assert 'question_text' in saved_data[str(q_num)]
    
    file_path.unlink()
    print(f"✓ All {num_questions} answers saved correctly with {num_threads} concurrent threads")


def test_rapid_sequential_submission():
    """Test rapid sequential answer submissions"""
    test_email = "test_rapid@example.com"
    num_questions = 30
    
    pdn_file_path = PDNFilePath()
    filename = f"{test_email}_answers.json"
    file_path = pdn_file_path.get_user_file_path(test_email, filename)
    if file_path.exists():
        file_path.unlink()
    
    for q_num in range(1, num_questions + 1):
        answer_data = {
            'selected_option_code': f'Q{q_num}_CODE',
            'ranking': None
        }
        save_answer(test_email, q_num, answer_data, f"Question {q_num}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        saved_data = json.load(f)
    
    assert len([k for k in saved_data.keys() if k != 'metadata']) == num_questions
    
    file_path.unlink()
    print(f"✓ All {num_questions} rapid sequential answers saved correctly")


if __name__ == '__main__':
    test_concurrent_answer_submission()
    test_rapid_sequential_submission()
    print("\n✓ All race condition tests passed!")
