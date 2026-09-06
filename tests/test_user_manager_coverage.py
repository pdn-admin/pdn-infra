"""Tests for UserManager to achieve >90% code coverage.

Tests user CRUD operations, validation, singleton pattern,
file persistence, PDN code discovery, password hashing/verification,
plaintext password migration, and mocked file I/O.
"""

import json
import pytest
import bcrypt
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from tempfile import NamedTemporaryFile, TemporaryDirectory

from app.pdn_chat_ai.user_manager import UserManager, get_user_manager, _EMAIL_PATTERN


@pytest.fixture
def temp_users_file(tmp_path):
    """Create a temporary users.json file with test data."""
    users_file = tmp_path / "users.json"
    test_users = {
        'test@example.com': {
            'password': 'testpass',
            'pdn_code': 'a3',
            'name': 'Test User',
            'gender': 'male',
            'daily_conversation_limit': 15,
            'created_at': '2025-01-01 00:00'
        },
        'admin@example.com': {
            'password': 'adminpass',
            'pdn_code': 'e5',
            'name': 'Admin User',
            'gender': 'female',
            'daily_conversation_limit': 100,
            'created_at': '2025-01-01 00:00'
        }
    }
    users_file.write_text(json.dumps(test_users, ensure_ascii=False), encoding='utf-8')
    return users_file


@pytest.fixture
def user_manager(temp_users_file, tmp_path):
    """Create a UserManager with a temp file and mock prompts dir."""
    # Create mock prompts directory with some .prompt files
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "a3.prompt").write_text("prompt content")
    (prompts_dir / "e5.prompt").write_text("prompt content")
    (prompts_dir / "p10.prompt").write_text("prompt content")

    um = UserManager(json_path=temp_users_file)
    # Override PROMPTS_DIR to use our temp directory
    um.PROMPTS_DIR = prompts_dir
    return um


class TestGetUser:
    """Tests for get_user method."""

    def test_get_user_valid_email(self, user_manager):
        """Returns user data for existing email."""
        user = user_manager.get_user('test@example.com')
        assert user is not None
        assert user['name'] == 'Test User'
        # Password is now bcrypt-hashed on load (auto-migration)
        assert user['password'].startswith('$2b$')
        assert user['pdn_code'] == 'a3'

    def test_get_user_invalid_email(self, user_manager):
        """Returns None for non-existent email."""
        user = user_manager.get_user('nonexistent@example.com')
        assert user is None

    def test_get_user_returns_copy(self, user_manager):
        """Returned dict is a copy, not a reference."""
        user = user_manager.get_user('test@example.com')
        user['name'] = 'Modified'
        original = user_manager.get_user('test@example.com')
        assert original['name'] == 'Test User'


class TestGetAllUsers:
    """Tests for get_all_users method."""

    def test_get_all_users(self, user_manager):
        """Returns list of all users without passwords."""
        users = user_manager.get_all_users()
        assert len(users) == 2
        for user in users:
            assert 'password' not in user
            assert 'email' in user
            assert 'name' in user
            assert 'pdn_code' in user

    def test_get_all_users_has_expected_fields(self, user_manager):
        """Each user dict has the expected fields."""
        users = user_manager.get_all_users()
        expected_fields = {'email', 'name', 'gender', 'pdn_code', 'daily_conversation_limit', 'created_at'}
        for user in users:
            assert set(user.keys()) == expected_fields


class TestAddUser:
    """Tests for add_user method."""

    def test_add_user_success(self, user_manager):
        """Successfully adds a new user."""
        result = user_manager.add_user(
            email='new@example.com',
            password='newpass',
            name='New User',
            pdn_code='a3',
            daily_conversation_limit=20,
            gender='female'
        )
        assert result['email'] == 'new@example.com'
        assert result['name'] == 'New User'
        assert result['pdn_code'] == 'a3'
        assert result['daily_conversation_limit'] == 20

        # Verify user is persisted with hashed password
        user = user_manager.get_user('new@example.com')
        assert user is not None
        assert user['password'].startswith('$2b$')
        # Verify password can be verified
        assert user_manager.verify_password('new@example.com', 'newpass') is True

    def test_add_user_email_normalized(self, user_manager):
        """Email is lowercased and stripped."""
        result = user_manager.add_user(
            email='  NEW@EXAMPLE.COM  ',
            password='pass',
            name='User',
            pdn_code='a3'
        )
        assert result['email'] == 'new@example.com'

    def test_add_user_duplicate_email(self, user_manager):
        """Raises ValueError for duplicate email."""
        with pytest.raises(ValueError, match="כבר קיים"):
            user_manager.add_user(
                email='test@example.com',
                password='pass',
                name='Duplicate',
                pdn_code='a3'
            )

    def test_add_user_invalid_email(self, user_manager):
        """Raises ValueError for invalid email format."""
        with pytest.raises(ValueError, match="אימייל"):
            user_manager.add_user(
                email='not-an-email',
                password='pass',
                name='User',
                pdn_code='a3'
            )

    def test_add_user_empty_password(self, user_manager):
        """Raises ValueError for empty password."""
        with pytest.raises(ValueError, match="סיסמה"):
            user_manager.add_user(
                email='valid@example.com',
                password='',
                name='User',
                pdn_code='a3'
            )

    def test_add_user_empty_name(self, user_manager):
        """Raises ValueError for empty name."""
        with pytest.raises(ValueError, match="שם"):
            user_manager.add_user(
                email='valid@example.com',
                password='pass',
                name='   ',
                pdn_code='a3'
            )

    def test_add_user_invalid_gender(self, user_manager):
        """Raises ValueError for invalid gender."""
        with pytest.raises(ValueError, match="מין"):
            user_manager.add_user(
                email='valid@example.com',
                password='pass',
                name='User',
                pdn_code='a3',
                gender='other'
            )

    def test_add_user_invalid_pdn_code(self, user_manager):
        """Raises ValueError for invalid PDN code."""
        with pytest.raises(ValueError, match="PDN"):
            user_manager.add_user(
                email='valid@example.com',
                password='pass',
                name='User',
                pdn_code='invalid_code'
            )

    def test_add_user_invalid_daily_limit(self, user_manager):
        """Raises ValueError for invalid daily limit."""
        with pytest.raises(ValueError, match="מגבלת שיחות"):
            user_manager.add_user(
                email='valid@example.com',
                password='pass',
                name='User',
                pdn_code='a3',
                daily_conversation_limit=0
            )

    def test_add_user_non_int_daily_limit(self, user_manager):
        """Raises ValueError for non-integer daily limit."""
        with pytest.raises(ValueError, match="מגבלת שיחות"):
            user_manager.add_user(
                email='valid@example.com',
                password='pass',
                name='User',
                pdn_code='a3',
                daily_conversation_limit='abc'
            )


class TestUpdateUser:
    """Tests for update_user method."""

    def test_update_user_name(self, user_manager):
        """Successfully updates user name."""
        result = user_manager.update_user('test@example.com', name='Updated Name')
        assert result['name'] == 'Updated Name'

    def test_update_user_pdn_code(self, user_manager):
        """Successfully updates PDN code."""
        result = user_manager.update_user('test@example.com', pdn_code='e5')
        assert result['pdn_code'] == 'e5'

    def test_update_user_daily_limit(self, user_manager):
        """Successfully updates daily conversation limit."""
        result = user_manager.update_user('test@example.com', daily_conversation_limit=50)
        assert result['daily_conversation_limit'] == 50

    def test_update_user_not_found(self, user_manager):
        """Raises KeyError for non-existent user."""
        with pytest.raises(KeyError):
            user_manager.update_user('missing@example.com', name='Test')

    def test_update_user_invalid_pdn_code(self, user_manager):
        """Raises ValueError for invalid PDN code."""
        with pytest.raises(ValueError, match="PDN"):
            user_manager.update_user('test@example.com', pdn_code='invalid')

    def test_update_user_invalid_daily_limit(self, user_manager):
        """Raises ValueError for invalid daily limit."""
        with pytest.raises(ValueError, match="מגבלת שיחות"):
            user_manager.update_user('test@example.com', daily_conversation_limit=0)

    def test_update_user_empty_name(self, user_manager):
        """Raises ValueError for empty name."""
        with pytest.raises(ValueError, match="שם"):
            user_manager.update_user('test@example.com', name='')

    def test_update_user_invalid_gender(self, user_manager):
        """Raises ValueError for invalid gender."""
        with pytest.raises(ValueError, match="מין"):
            user_manager.update_user('test@example.com', gender='other')

    def test_update_user_ignores_unknown_fields(self, user_manager):
        """Unknown fields are silently ignored."""
        result = user_manager.update_user('test@example.com', unknown_field='value')
        assert result['name'] == 'Test User'  # unchanged


class TestDeleteUser:
    """Tests for delete_user method."""

    def test_delete_user_success(self, user_manager):
        """Successfully deletes a user."""
        user_manager.delete_user('test@example.com')
        assert user_manager.get_user('test@example.com') is None

    def test_delete_user_not_found(self, user_manager):
        """Raises KeyError for non-existent user."""
        with pytest.raises(KeyError):
            user_manager.delete_user('missing@example.com')


class TestGetAvailablePDNCodes:
    """Tests for get_available_pdn_codes method."""

    def test_get_available_pdn_codes(self, user_manager):
        """Returns sorted list of PDN codes from prompt files."""
        codes = user_manager.get_available_pdn_codes()
        assert codes == ['a3', 'e5', 'p10']

    def test_get_available_pdn_codes_no_dir(self, user_manager, tmp_path):
        """Returns empty list when prompts directory doesn't exist."""
        user_manager.PROMPTS_DIR = tmp_path / "nonexistent"
        codes = user_manager.get_available_pdn_codes()
        assert codes == []


class TestValidateEmail:
    """Tests for validate_email static method."""

    def test_valid_emails(self):
        """Valid email formats pass validation."""
        assert UserManager.validate_email('user@example.com') is True
        assert UserManager.validate_email('user.name@domain.co.il') is True
        assert UserManager.validate_email('user+tag@example.com') is True

    def test_invalid_emails(self):
        """Invalid email formats fail validation."""
        assert UserManager.validate_email('') is False
        assert UserManager.validate_email('not-an-email') is False
        assert UserManager.validate_email('@domain.com') is False
        assert UserManager.validate_email('user@') is False
        assert UserManager.validate_email('user@.com') is False


class TestFileLoading:
    """Tests for file loading and persistence."""

    def test_load_from_existing_file(self, temp_users_file):
        """Loads users from existing JSON file."""
        um = UserManager(json_path=temp_users_file)
        assert um.get_user('test@example.com') is not None

    def test_seed_when_file_missing(self, tmp_path):
        """Seeds from _SEED_USERS when file doesn't exist."""
        missing_file = tmp_path / "missing.json"
        um = UserManager(json_path=missing_file)
        # Should have seeded users
        assert um.get_user('tomergur@gmail.com') is not None
        # File should now exist
        assert missing_file.exists()

    def test_seed_when_file_corrupt(self, tmp_path):
        """Seeds from _SEED_USERS when file is corrupt."""
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("not valid json {{{", encoding='utf-8')
        um = UserManager(json_path=corrupt_file)
        # Should have seeded users
        assert um.get_user('tomergur@gmail.com') is not None

    def test_seed_when_file_empty_dict(self, tmp_path):
        """Seeds from _SEED_USERS when file contains empty dict."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}", encoding='utf-8')
        um = UserManager(json_path=empty_file)
        # Should have seeded users
        assert um.get_user('tomergur@gmail.com') is not None

    def test_persistence_after_add(self, temp_users_file, tmp_path):
        """Adding a user persists to file."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "a3.prompt").write_text("content")

        um = UserManager(json_path=temp_users_file)
        um.PROMPTS_DIR = prompts_dir
        um.add_user('new@example.com', 'pass', 'New', 'a3')

        # Reload from file
        um2 = UserManager(json_path=temp_users_file)
        assert um2.get_user('new@example.com') is not None

    def test_persistence_after_delete(self, temp_users_file):
        """Deleting a user persists to file."""
        um = UserManager(json_path=temp_users_file)
        um.delete_user('test@example.com')

        # Reload from file
        um2 = UserManager(json_path=temp_users_file)
        assert um2.get_user('test@example.com') is None


class TestSingleton:
    """Tests for the get_user_manager singleton."""

    def test_singleton_returns_same_instance(self):
        """get_user_manager returns the same instance on repeated calls."""
        import app.pdn_chat_ai.user_manager as um_module
        # Reset singleton
        um_module._user_manager = None

        with patch.object(UserManager, '__init__', return_value=None) as mock_init:
            mock_init.return_value = None
            # First call creates instance
            um_module._user_manager = None
            mgr1 = get_user_manager()
            mgr2 = get_user_manager()
            assert mgr1 is mgr2

    def test_singleton_creates_instance_when_none(self):
        """get_user_manager creates a new instance when _user_manager is None."""
        import app.pdn_chat_ai.user_manager as um_module
        old = um_module._user_manager
        um_module._user_manager = None
        try:
            mgr = get_user_manager()
            assert mgr is not None
            assert isinstance(mgr, UserManager)
        finally:
            um_module._user_manager = old



class TestVerifyPassword:
    """Tests for verify_password method - correct, incorrect, non-existent user (timing-safe)."""

    def test_verify_password_correct(self, user_manager):
        """verify_password returns True for correct password after bcrypt migration."""
        # The fixture loads users with plaintext 'testpass' which gets migrated to bcrypt
        assert user_manager.verify_password('test@example.com', 'testpass') is True

    def test_verify_password_incorrect(self, user_manager):
        """verify_password returns False for incorrect password."""
        assert user_manager.verify_password('test@example.com', 'wrongpass') is False

    def test_verify_password_nonexistent_user_timing_safe(self, user_manager):
        """verify_password returns False for non-existent user with timing-safe dummy hash."""
        # This should not raise and should perform a dummy hash to prevent timing attacks
        result = user_manager.verify_password('nonexistent@example.com', 'anypass')
        assert result is False

    def test_verify_password_email_normalized(self, user_manager):
        """verify_password normalizes email (lowercase, strip)."""
        assert user_manager.verify_password('  TEST@EXAMPLE.COM  ', 'testpass') is True

    def test_verify_password_with_newly_added_user(self, user_manager):
        """verify_password works for a freshly added user with bcrypt-hashed password."""
        user_manager.add_user(
            email='fresh@example.com',
            password='freshpass123',
            name='Fresh User',
            pdn_code='a3'
        )
        assert user_manager.verify_password('fresh@example.com', 'freshpass123') is True
        assert user_manager.verify_password('fresh@example.com', 'wrongpass') is False


class TestUpdateUserPasswordRehashing:
    """Tests for update_user password re-hashing behavior."""

    def test_update_user_password_rehashes(self, user_manager):
        """Updating password stores a new bcrypt hash."""
        user_manager.update_user('test@example.com', password='newpassword')
        user = user_manager.get_user('test@example.com')
        # Password should be bcrypt-hashed
        assert user['password'].startswith('$2b$')
        # New password should verify
        assert user_manager.verify_password('test@example.com', 'newpassword') is True
        # Old password should not verify
        assert user_manager.verify_password('test@example.com', 'testpass') is False

    def test_update_user_password_different_hash_each_time(self, user_manager):
        """Each password update produces a different bcrypt hash (different salt)."""
        user_manager.update_user('test@example.com', password='samepass')
        hash1 = user_manager.get_user('test@example.com')['password']
        user_manager.update_user('test@example.com', password='samepass')
        hash2 = user_manager.get_user('test@example.com')['password']
        # Different salts produce different hashes
        assert hash1 != hash2
        # Both should still verify
        assert user_manager.verify_password('test@example.com', 'samepass') is True

    def test_update_user_gender_valid_values(self, user_manager):
        """Updating gender with valid values succeeds."""
        result = user_manager.update_user('test@example.com', gender='female')
        assert result['gender'] == 'female'
        result = user_manager.update_user('test@example.com', gender='male')
        assert result['gender'] == 'male'
        # Empty string is allowed (clears gender)
        result = user_manager.update_user('test@example.com', gender='')
        assert result['gender'] == ''


class TestMigratePlaintextPasswords:
    """Tests for _migrate_plaintext_passwords converting plaintext to bcrypt."""

    def test_migrate_converts_plaintext_to_bcrypt(self, tmp_path):
        """Plaintext passwords are converted to bcrypt hashes on initialization."""
        users_file = tmp_path / "users.json"
        test_users = {
            'user1@example.com': {
                'password': 'plaintext1',
                'pdn_code': 'a3',
                'name': 'User 1',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            },
            'user2@example.com': {
                'password': 'plaintext2',
                'pdn_code': 'e5',
                'name': 'User 2',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        }
        users_file.write_text(json.dumps(test_users), encoding='utf-8')

        um = UserManager(json_path=users_file)

        # Both passwords should now be bcrypt hashes
        user1 = um.get_user('user1@example.com')
        user2 = um.get_user('user2@example.com')
        assert user1['password'].startswith('$2b$')
        assert user2['password'].startswith('$2b$')

        # Original plaintext passwords should still verify
        assert um.verify_password('user1@example.com', 'plaintext1') is True
        assert um.verify_password('user2@example.com', 'plaintext2') is True

    def test_migrate_skips_already_hashed_passwords(self, tmp_path):
        """Already-hashed passwords are not re-hashed during migration."""
        existing_hash = bcrypt.hashpw(b'already_hashed', bcrypt.gensalt()).decode('utf-8')
        users_file = tmp_path / "users.json"
        test_users = {
            'hashed@example.com': {
                'password': existing_hash,
                'pdn_code': 'a3',
                'name': 'Hashed User',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        }
        users_file.write_text(json.dumps(test_users), encoding='utf-8')

        um = UserManager(json_path=users_file)

        # Password should remain the same hash
        user = um.get_user('hashed@example.com')
        assert user['password'] == existing_hash
        assert um.verify_password('hashed@example.com', 'already_hashed') is True

    def test_migrate_persists_to_file(self, tmp_path):
        """Migration saves the updated hashes to the JSON file."""
        users_file = tmp_path / "users.json"
        test_users = {
            'migrate@example.com': {
                'password': 'plain',
                'pdn_code': 'a3',
                'name': 'Migrate User',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        }
        users_file.write_text(json.dumps(test_users), encoding='utf-8')

        um = UserManager(json_path=users_file)

        # Reload from file to verify persistence
        data = json.loads(users_file.read_text(encoding='utf-8'))
        assert data['migrate@example.com']['password'].startswith('$2b$')


class TestGetAvailablePDNCodesMocked:
    """Tests for get_available_pdn_codes with mocked PROMPTS_DIR."""

    def test_get_available_pdn_codes_with_mock_dir(self, tmp_path):
        """Returns sorted list of .prompt file stems from mocked directory."""
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps({
            'x@x.com': {'password': 'p', 'pdn_code': 'a3', 'name': 'X',
                        'gender': '', 'daily_conversation_limit': 10,
                        'created_at': '2025-01-01 00:00'}
        }), encoding='utf-8')

        prompts_dir = tmp_path / "mock_prompts"
        prompts_dir.mkdir()
        (prompts_dir / "t4.prompt").write_text("content")
        (prompts_dir / "a7.prompt").write_text("content")
        (prompts_dir / "e1.prompt").write_text("content")
        (prompts_dir / "not_a_prompt.txt").write_text("ignored")

        um = UserManager(json_path=users_file)
        um.PROMPTS_DIR = prompts_dir

        codes = um.get_available_pdn_codes()
        assert codes == ['a7', 'e1', 't4']
        # .txt file should not be included
        assert 'not_a_prompt' not in codes

    def test_get_available_pdn_codes_empty_dir(self, tmp_path):
        """Returns empty list when prompts directory has no .prompt files."""
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps({
            'x@x.com': {'password': 'p', 'pdn_code': 'a3', 'name': 'X',
                        'gender': '', 'daily_conversation_limit': 10,
                        'created_at': '2025-01-01 00:00'}
        }), encoding='utf-8')

        prompts_dir = tmp_path / "empty_prompts"
        prompts_dir.mkdir()

        um = UserManager(json_path=users_file)
        um.PROMPTS_DIR = prompts_dir

        codes = um.get_available_pdn_codes()
        assert codes == []


class TestMockedFileIO:
    """Tests that mock JSON file I/O for _save_to_file and _load_users."""

    def test_save_to_file_writes_json(self, tmp_path):
        """_save_to_file writes users as JSON to the configured path."""
        users_file = tmp_path / "users.json"
        test_users = {
            'test@example.com': {
                'password': 'pass',
                'pdn_code': 'a3',
                'name': 'Test',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        }
        users_file.write_text(json.dumps(test_users), encoding='utf-8')

        um = UserManager(json_path=users_file)

        # Verify the file was written (migration triggers save)
        data = json.loads(users_file.read_text(encoding='utf-8'))
        assert 'test@example.com' in data

    @patch('pathlib.Path.write_text')
    @patch('pathlib.Path.replace')
    @patch('pathlib.Path.mkdir')
    def test_save_to_file_uses_atomic_write(self, mock_mkdir, mock_replace, mock_write_text, tmp_path):
        """_save_to_file uses atomic write pattern (write to .tmp then replace)."""
        users_file = tmp_path / "users.json"
        test_users = {
            'test@example.com': {
                'password': '$2b$12$hashedpassword',
                'pdn_code': 'a3',
                'name': 'Test',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        }

        # Mock _load_users to avoid file system access
        with patch.object(UserManager, '_load_users') as mock_load, \
             patch.object(UserManager, '_migrate_plaintext_passwords'):
            um = UserManager(json_path=users_file)
            um._users = test_users

        # Now call _save_to_file
        um._save_to_file()

        # Verify atomic write pattern: mkdir, write_text to .tmp, replace
        mock_mkdir.assert_called()
        mock_write_text.assert_called_once()
        mock_replace.assert_called_once()

    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.read_text')
    def test_load_users_reads_from_json_file(self, mock_read_text, mock_exists):
        """_load_users reads and parses JSON from the configured path."""
        test_data = json.dumps({
            'loaded@example.com': {
                'password': '$2b$12$alreadyhashed',
                'pdn_code': 'a3',
                'name': 'Loaded',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        })
        mock_read_text.return_value = test_data

        with patch.object(UserManager, '_migrate_plaintext_passwords'):
            um = UserManager.__new__(UserManager)
            um._json_path = Path('/fake/users.json')
            um._users = {}
            um._lock = __import__('threading').Lock()
            um._load_users()

        assert 'loaded@example.com' in um._users
        assert um._users['loaded@example.com']['name'] == 'Loaded'

    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.read_text', side_effect=json.JSONDecodeError("err", "", 0))
    def test_load_users_falls_back_on_corrupt_json(self, mock_read_text, mock_exists):
        """_load_users falls back to seed data when JSON is corrupt."""
        with patch.object(UserManager, '_migrate_plaintext_passwords'), \
             patch.object(UserManager, '_save_to_file'):
            um = UserManager.__new__(UserManager)
            um._json_path = Path('/fake/users.json')
            um._users = {}
            um._lock = __import__('threading').Lock()
            um._load_users()

        # Should have seeded users
        assert 'tomergur@gmail.com' in um._users

    @patch('pathlib.Path.exists', return_value=False)
    def test_load_users_seeds_when_file_missing(self, mock_exists):
        """_load_users seeds from _SEED_USERS when file doesn't exist."""
        with patch.object(UserManager, '_migrate_plaintext_passwords'), \
             patch.object(UserManager, '_save_to_file'):
            um = UserManager.__new__(UserManager)
            um._json_path = Path('/fake/users.json')
            um._users = {}
            um._lock = __import__('threading').Lock()
            um._load_users()

        # Should have seeded users
        assert 'tomergur@gmail.com' in um._users
        assert 'pdncode@gmail.com' in um._users


# ============================================================================
# Property-Based Tests (Hypothesis)
# ============================================================================

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st


# --- Strategies ---

# Valid email strategy
valid_emails = st.from_regex(r'[a-z]{3,10}@[a-z]{3,8}\.[a-z]{2,4}', fullmatch=True)

# Invalid email strategy: strings that don't match the email pattern
invalid_emails = st.one_of(
    st.just(""),
    st.just("no-at-sign"),
    st.just("@domain.com"),
    st.just("user@"),
    st.just("user@.com"),
    st.from_regex(r'[a-z]{3,10}', fullmatch=True),  # no @ at all
    st.from_regex(r'[a-z]{3,10}@[a-z]{3,8}', fullmatch=True),  # no TLD
)

# Valid PDN codes (matching what the test prompts dir provides)
valid_pdn_codes = st.sampled_from(["a3", "e5", "p10"])

# Invalid PDN codes
invalid_pdn_codes = st.text(min_size=1, max_size=10).filter(
    lambda x: x not in ("a3", "e5", "p10")
)

# Password strategy (non-empty, reasonable length for bcrypt)
passwords = st.text(
    alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=30
)


class TestPropertyUserCreationValidation:
    """Property 10: User Creation Validation Rules.

    **Validates: Requirements 6.2**

    Invalid email format → ValueError; invalid pdn_code → ValueError; duplicate email → ValueError.
    """

    @given(email=invalid_emails)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_email_raises_value_error(self, email, user_manager):
        """For any email that doesn't match the valid pattern, add_user raises ValueError."""
        # Ensure the email is actually invalid per the regex
        assume(not _EMAIL_PATTERN.match(email))
        with pytest.raises(ValueError):
            user_manager.add_user(
                email=email,
                password='validpass',
                name='Test User',
                pdn_code='a3'
            )

    @given(pdn_code=invalid_pdn_codes)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_pdn_code_raises_value_error(self, pdn_code, user_manager):
        """For any pdn_code not in available codes, add_user raises ValueError."""
        with pytest.raises(ValueError):
            user_manager.add_user(
                email='unique_prop_test@example.com',
                password='validpass',
                name='Test User',
                pdn_code=pdn_code
            )

    @given(email=valid_emails)
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_duplicate_email_raises_value_error(self, email, tmp_path):
        """For any email already in the store, add_user raises ValueError."""
        # Create isolated user manager per example to avoid state leakage
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps({}), encoding='utf-8')

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir(exist_ok=True)
        (prompts_dir / "a3.prompt").write_text("content", encoding='utf-8')

        um = UserManager(json_path=users_file)
        um.PROMPTS_DIR = prompts_dir

        # First add should succeed
        um.add_user(
            email=email,
            password='pass1',
            name='First User',
            pdn_code='a3'
        )

        # Second add with same email should raise ValueError
        with pytest.raises(ValueError):
            um.add_user(
                email=email,
                password='pass2',
                name='Second User',
                pdn_code='a3'
            )


class TestPropertyPasswordHashRoundTrip:
    """Property 11: Password Hash Round-Trip.

    **Validates: Requirements 6.3**

    verify_password(email, P) → True; verify_password(email, Q≠P) → False.
    """

    # Short password strategy for bcrypt performance (max 8 chars)
    short_passwords = st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=8
    )

    @given(password=short_passwords, wrong_password=short_passwords)
    @settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    def test_password_round_trip(self, password, wrong_password, tmp_path):
        """For any user created with password P, verify_password(email, P) returns True,
        and for any Q ≠ P, verify_password(email, Q) returns False."""
        assume(password != wrong_password)

        # Set up isolated user manager
        users_file = tmp_path / "users.json"
        users_file.write_text(json.dumps({}), encoding='utf-8')

        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir(exist_ok=True)
        (prompts_dir / "a3.prompt").write_text("content", encoding='utf-8')

        um = UserManager(json_path=users_file)
        um.PROMPTS_DIR = prompts_dir

        email = 'proptest@example.com'
        um.add_user(email=email, password=password, name='Prop User', pdn_code='a3')

        # Correct password verifies
        assert um.verify_password(email, password) is True
        # Wrong password does not verify
        assert um.verify_password(email, wrong_password) is False


class TestPropertyUserUpdateValidation:
    """Property 12: User Update Validation Rules.

    **Validates: Requirements 6.4**

    Invalid pdn_code, non-positive limit, empty name, invalid gender → ValueError.
    """

    @given(pdn_code=invalid_pdn_codes)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_pdn_code_update_raises(self, pdn_code, user_manager):
        """For any pdn_code not in available codes, update_user raises ValueError."""
        with pytest.raises(ValueError):
            user_manager.update_user('test@example.com', pdn_code=pdn_code)

    @given(limit=st.one_of(
        st.integers(max_value=0),
        st.just(0),
        st.just(-1),
        st.just(-100),
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_positive_limit_raises(self, limit, user_manager):
        """For any non-positive daily_conversation_limit, update_user raises ValueError."""
        with pytest.raises(ValueError):
            user_manager.update_user('test@example.com', daily_conversation_limit=limit)

    @given(name=st.one_of(
        st.just(''),
        st.just('   '),
        st.just('\t'),
        st.just('\n'),
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_empty_name_raises(self, name, user_manager):
        """For any empty name (or whitespace-only), update_user raises ValueError."""
        with pytest.raises(ValueError):
            user_manager.update_user('test@example.com', name=name)

    @given(gender=st.text(min_size=1, max_size=20).filter(
        lambda g: g not in ('male', 'female', '')
    ))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_gender_raises(self, gender, user_manager):
        """For any gender not in {'male', 'female', ''}, update_user raises ValueError."""
        with pytest.raises(ValueError):
            user_manager.update_user('test@example.com', gender=gender)


class TestPropertyPlaintextPasswordMigration:
    """Property 13: Plaintext Password Migration.

    **Validates: Requirements 6.6**

    After migration, stored password starts with $2b$ and original verifies correctly.
    """

    @given(password=st.text(
        alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=8
    ))
    @settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
    def test_plaintext_migration_produces_bcrypt_and_verifies(self, password, tmp_path):
        """For any plaintext password, after migration it starts with $2b$ and
        the original password still verifies correctly."""
        assume(not password.startswith('$2b$'))

        users_file = tmp_path / "users.json"
        test_users = {
            'migrate@example.com': {
                'password': password,
                'pdn_code': 'a3',
                'name': 'Migrate User',
                'gender': '',
                'daily_conversation_limit': 15,
                'created_at': '2025-01-01 00:00'
            }
        }
        users_file.write_text(json.dumps(test_users, ensure_ascii=False), encoding='utf-8')

        um = UserManager(json_path=users_file)

        # After initialization (which triggers migration), password should be bcrypt
        user = um.get_user('migrate@example.com')
        assert user['password'].startswith('$2b$'), \
            f"Expected bcrypt hash starting with $2b$, got: {user['password'][:10]}"

        # Original password should still verify
        assert um.verify_password('migrate@example.com', password) is True
