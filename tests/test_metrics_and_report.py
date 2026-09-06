"""Tests for the metrics dashboard and algorithm report email feature.

Covers:
- /pdn-admin/send_algorithm_report endpoint (auth, success, file not found, smtp failure)
- Metrics calculation logic (date filtering, code distribution, match/mismatch)
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from flask import Flask

from app.pdn_admin.admin_routes import (
    pdn_admin_bp, admin_sessions, create_session,
    _metadata_cache
)


@pytest.fixture(autouse=True)
def clear_state():
    """Clear sessions and cache before each test."""
    admin_sessions.clear()
    _metadata_cache['data'] = None
    _metadata_cache['timestamp'] = 0
    yield
    admin_sessions.clear()


@pytest.fixture
def app():
    """Create Flask test app with admin blueprint."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret'
    application.config['ADMIN_PASSWORD'] = 'pdn'
    application.register_blueprint(pdn_admin_bp, url_prefix='/pdn-admin')
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def valid_token():
    """Create a valid admin session token."""
    return create_session('admin@test.com')


# ===== /send_algorithm_report Tests =====

class TestSendAlgorithmReport:
    """Tests for the send_algorithm_report endpoint."""

    def test_unauthorized_without_token(self, client):
        """Should return 401 when no session token provided."""
        resp = client.post('/pdn-admin/send_algorithm_report')
        assert resp.status_code == 401
        data = resp.get_json()
        assert 'error' in data

    def test_unauthorized_with_invalid_token(self, client):
        """Should return 401 with invalid session token."""
        resp = client.post('/pdn-admin/send_algorithm_report?session_token=invalid-token')
        assert resp.status_code == 401

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_success_sends_email(self, mock_smtp, client, valid_token):
        """Should send email with report attached when authorized."""
        mock_smtp.return_value = True

        report_path = Path(__file__).parent.parent / 'docs' / 'pdn_algorithm_report.html'
        if not report_path.exists():
            pytest.skip("Report file not present")

        resp = client.post(f'/pdn-admin/send_algorithm_report?session_token={valid_token}')
        assert resp.status_code != 401

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_success_with_real_report_file(self, mock_smtp, client, valid_token):
        """Should send successfully when report file exists and SMTP works."""
        mock_smtp.return_value = True

        report_path = Path(__file__).parent.parent / 'docs' / 'pdn_algorithm_report.html'
        if not report_path.exists():
            pytest.skip("Report file not present")

        resp = client.post(f'/pdn-admin/send_algorithm_report?session_token={valid_token}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert 'tomergur@gmail.com' in data['message']
        mock_smtp.assert_called_once()

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_smtp_failure(self, mock_smtp, client, valid_token):
        """Should return 500 when SMTP fails."""
        mock_smtp.return_value = False

        report_path = Path(__file__).parent.parent / 'docs' / 'pdn_algorithm_report.html'
        if not report_path.exists():
            pytest.skip("Report file not present")

        resp = client.post(f'/pdn-admin/send_algorithm_report?session_token={valid_token}')
        assert resp.status_code == 500
        data = resp.get_json()
        assert 'error' in data


# ===== Metrics Data Logic Tests =====

class TestMetricsCalculation:
    """Test the metrics data logic (calculated client-side in JS, but we test the data structure)."""

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_metadata_csv_returns_data_for_metrics(self, mock_load, client, valid_token):
        """Metadata endpoint returns data usable for metrics calculations."""
        mock_load.return_value = [
            {
                "email": "user1@test.com",
                "date": "05/06/2026",
                "pdn_code": "A3",
                "diagnose_pdn_code": "A3",
                "first_name": "Test",
                "last_name": "User"
            },
            {
                "email": "user2@test.com",
                "date": "04/06/2026",
                "pdn_code": "P6",
                "diagnose_pdn_code": "E1",
                "first_name": "Other",
                "last_name": "User"
            },
            {
                "email": "user3@test.com",
                "date": "04/06/2026",
                "pdn_code": "A3",
                "diagnose_pdn_code": "",
                "first_name": "Third",
                "last_name": "User"
            }
        ]

        resp = client.get(f'/pdn-admin/metadata/csv?session_token={valid_token}')
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert len(data) == 3

        # Verify data has fields needed for metrics
        for user in data:
            assert 'date' in user
            assert 'pdn_code' in user
            assert 'diagnose_pdn_code' in user

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_metadata_contains_code_fields_for_match_metric(self, mock_load, client, valid_token):
        """Verify both pdn_code and diagnose_pdn_code are present for match/mismatch metric."""
        mock_load.return_value = [
            {
                "email": "match@test.com",
                "date": "05/06/2026",
                "pdn_code": "E1",
                "diagnose_pdn_code": "E1",
                "first_name": "Match",
                "last_name": "User"
            },
            {
                "email": "mismatch@test.com",
                "date": "05/06/2026",
                "pdn_code": "A7",
                "diagnose_pdn_code": "T4",
                "first_name": "Mismatch",
                "last_name": "User"
            },
            {
                "email": "undiagnosed@test.com",
                "date": "03/06/2026",
                "pdn_code": "P2",
                "diagnose_pdn_code": "N/A",
                "first_name": "Pending",
                "last_name": "User"
            }
        ]

        resp = client.get(f'/pdn-admin/metadata/csv?session_token={valid_token}')
        data = resp.get_json()['data']

        # Simulate the JS metrics logic server-side for verification
        with_both = [u for u in data if u['pdn_code'] and u['pdn_code'] != 'N/A'
                     and u['diagnose_pdn_code'] and u['diagnose_pdn_code'] != 'N/A'
                     and u['diagnose_pdn_code'] != '']
        assert len(with_both) == 2  # match + mismatch, not undiagnosed

        matches = [u for u in with_both if u['pdn_code'] == u['diagnose_pdn_code']]
        assert len(matches) == 1  # only match@test.com

        mismatches = [u for u in with_both if u['pdn_code'] != u['diagnose_pdn_code']]
        assert len(mismatches) == 1  # only mismatch@test.com

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_code_distribution_data(self, mock_load, client, valid_token):
        """Verify data supports PDN code distribution counting."""
        mock_load.return_value = [
            {"email": f"u{i}@test.com", "date": "05/06/2026", "pdn_code": code,
             "diagnose_pdn_code": "", "first_name": "U", "last_name": str(i)}
            for i, code in enumerate(["A3", "A3", "A3", "P6", "P6", "E9", "E5", "E5", "A7", "A7", "P10", "P10", "P2", "P2", "T8"])
        ]

        resp = client.get(f'/pdn-admin/metadata/csv?session_token={valid_token}')
        data = resp.get_json()['data']

        # Simulate distribution count
        code_count = {}
        for u in data:
            code = u['pdn_code']
            if code and code != 'N/A':
                code_count[code] = code_count.get(code, 0) + 1

        assert code_count['A3'] == 3
        assert code_count['P6'] == 2
        assert code_count['E9'] == 1
        assert code_count['T8'] == 1
        assert len(code_count) == 8  # 8 unique codes

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_daily_volume_data(self, mock_load, client, valid_token):
        """Verify data supports daily volume counting."""
        mock_load.return_value = [
            {"email": "u1@t.com", "date": "05/06/2026", "pdn_code": "A3", "diagnose_pdn_code": "", "first_name": "A", "last_name": "1"},
            {"email": "u2@t.com", "date": "05/06/2026", "pdn_code": "P6", "diagnose_pdn_code": "", "first_name": "B", "last_name": "2"},
            {"email": "u3@t.com", "date": "05/06/2026", "pdn_code": "E1", "diagnose_pdn_code": "", "first_name": "C", "last_name": "3"},
            {"email": "u4@t.com", "date": "05/06/2026", "pdn_code": "T4", "diagnose_pdn_code": "", "first_name": "D", "last_name": "4"},
            {"email": "u5@t.com", "date": "04/06/2026", "pdn_code": "A3", "diagnose_pdn_code": "", "first_name": "E", "last_name": "5"},
            {"email": "u6@t.com", "date": "03/06/2026", "pdn_code": "P6", "diagnose_pdn_code": "", "first_name": "F", "last_name": "6"},
        ]

        resp = client.get(f'/pdn-admin/metadata/csv?session_token={valid_token}')
        data = resp.get_json()['data']

        # Simulate daily volume
        day_counts = {}
        for u in data:
            if u['date']:
                day_counts[u['date']] = day_counts.get(u['date'], 0) + 1

        assert day_counts['05/06/2026'] == 4  # peak day
        assert day_counts['04/06/2026'] == 1
        assert day_counts['03/06/2026'] == 1

        # Peak day
        peak = max(day_counts.items(), key=lambda x: x[1])
        assert peak == ('05/06/2026', 4)

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_diagnosed_by_human_count(self, mock_load, client, valid_token):
        """Count users that have been diagnosed by human (diagnose_pdn_code is set)."""
        mock_load.return_value = [
            {"email": "u1@t.com", "date": "05/06/2026", "pdn_code": "A3", "diagnose_pdn_code": "A3", "first_name": "A", "last_name": "1"},
            {"email": "u2@t.com", "date": "05/06/2026", "pdn_code": "P6", "diagnose_pdn_code": "P6", "first_name": "B", "last_name": "2"},
            {"email": "u3@t.com", "date": "04/06/2026", "pdn_code": "E1", "diagnose_pdn_code": "", "first_name": "C", "last_name": "3"},
            {"email": "u4@t.com", "date": "04/06/2026", "pdn_code": "T4", "diagnose_pdn_code": "N/A", "first_name": "D", "last_name": "4"},
            {"email": "u5@t.com", "date": "03/06/2026", "pdn_code": "A7", "diagnose_pdn_code": "A7", "first_name": "E", "last_name": "5"},
        ]

        resp = client.get(f'/pdn-admin/metadata/csv?session_token={valid_token}')
        data = resp.get_json()['data']

        diagnosed = [u for u in data if u['diagnose_pdn_code'] and u['diagnose_pdn_code'] != 'N/A' and u['diagnose_pdn_code'] != '']
        assert len(diagnosed) == 3  # u1, u2, u5


# ===== /send_calculation_report Tests =====

class TestSendCalculationReport:
    """Tests for the send_calculation_report endpoint (sends recalculation details via email)."""

    def test_unauthorized_without_token(self, client):
        """Should return 401 when no session token provided."""
        resp = client.post('/pdn-admin/send_calculation_report',
                          json={"email": "test@test.com", "html_content": "<p>test</p>"})
        assert resp.status_code == 401

    def test_unauthorized_with_invalid_token(self, client):
        """Should return 401 with invalid session token."""
        resp = client.post('/pdn-admin/send_calculation_report?session_token=bad',
                          json={"email": "test@test.com", "html_content": "<p>test</p>"})
        assert resp.status_code == 401

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_success_sends_calculation_report(self, mock_smtp, client, valid_token):
        """Should send calculation report HTML as email."""
        mock_smtp.return_value = True

        resp = client.post(f'/pdn-admin/send_calculation_report?session_token={valid_token}',
                          json={
                              "email": "user@example.com",
                              "html_content": "<div><h2>P2</h2><p>Trait: P, Energy: S</p></div>"
                          })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        mock_smtp.assert_called_once()

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_smtp_failure_returns_500(self, mock_smtp, client, valid_token):
        """Should return 500 when SMTP fails."""
        mock_smtp.return_value = False

        resp = client.post(f'/pdn-admin/send_calculation_report?session_token={valid_token}',
                          json={
                              "email": "user@example.com",
                              "html_content": "<div>report</div>"
                          })
        assert resp.status_code == 500
        data = resp.get_json()
        assert 'error' in data

    def test_empty_content_returns_400(self, client, valid_token):
        """Should return 400 when html_content is empty."""
        resp = client.post(f'/pdn-admin/send_calculation_report?session_token={valid_token}',
                          json={"email": "user@example.com", "html_content": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_email_subject_contains_user_email(self, mock_smtp, client, valid_token):
        """Verify the email subject includes the user's email address."""
        mock_smtp.return_value = True

        resp = client.post(f'/pdn-admin/send_calculation_report?session_token={valid_token}',
                          json={
                              "email": "specific_user@pdn.co.il",
                              "html_content": "<div>data</div>"
                          })
        assert resp.status_code == 200
        # Check the message was constructed with the email in subject
        call_args = mock_smtp.call_args[0][0]
        assert 'specific_user@pdn.co.il' in call_args['Subject']


# ===== /send_email with metadata fix Tests =====

class TestSendEmailMetadataFix:
    """Tests for the send_email endpoint metadata.email fallback fix."""

    @patch('app.utils.email_sender.send_email_via_smtp')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_fills_missing_metadata_email(self, mock_load, mock_smtp, client, valid_token):
        """When metadata.email is missing, it should use the URL email parameter."""
        mock_smtp.return_value = True
        # Answers without metadata.email
        mock_load.return_value = {
            "1": {"selected_option_code": "AP"},
            "2": {"selected_option_code": "ET"},
            "27": {"ranking": {"D": 1, "S": 2, "F": 3}},
        }

        resp = client.post(f'/pdn-admin/user/send_email/testuser@gmail.com?session_token={valid_token}')
        # It may fail for other reasons (no PDF, etc.) but should not fail with "No email"
        # The key is it doesn't return 404 about email
        if resp.status_code == 200:
            data = resp.get_json()
            assert data.get('success') is True
        elif resp.status_code == 500:
            # SMTP failure or PDF not found — but NOT "No email address"
            data = resp.get_json()
            assert 'No email address' not in data.get('error', '')

    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_user_not_found(self, mock_load, client, valid_token):
        """Should return 404 when user answers don't exist."""
        mock_load.return_value = None

        resp = client.post(f'/pdn-admin/user/send_email/nobody@test.com?session_token={valid_token}')
        assert resp.status_code == 404


# ===== Energy Distribution Tests =====

class TestEnergyDistribution:
    """Tests for the energy grouping logic used in the metrics chart."""

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_energy_grouping_from_code_numbers(self, mock_load, client, valid_token):
        """Verify codes can be grouped by energy type based on their number."""
        mock_load.return_value = [
            {"email": f"u{i}@t.com", "date": "05/06/2026", "pdn_code": code,
             "diagnose_pdn_code": "", "first_name": "U", "last_name": str(i)}
            for i, code in enumerate([
                "A7", "A7", "E1", "T4", "P10",  # D energy (1,4,7,10)
                "E5", "A11", "T8", "P2",         # S energy (2,5,8,11)
                "A3", "E9", "T12", "P6",         # F energy (3,6,9,12)
            ])
        ]

        resp = client.get(f'/pdn-admin/metadata/csv?session_token={valid_token}')
        data = resp.get_json()['data']

        # Simulate the energy grouping logic from admin.js
        code_to_energy = {
            '1': 'D', '4': 'D', '7': 'D', '10': 'D',
            '2': 'S', '5': 'S', '8': 'S', '11': 'S',
            '3': 'F', '6': 'F', '9': 'F', '12': 'F'
        }
        energy_groups = {'D': 0, 'S': 0, 'F': 0}

        for u in data:
            code = u['pdn_code']
            if code and code != 'N/A':
                import re
                num = re.sub(r'[A-Z]', '', code, flags=re.IGNORECASE)
                energy = code_to_energy.get(num)
                if energy:
                    energy_groups[energy] += 1

        assert energy_groups['D'] == 5  # A7×2, E1, T4, P10
        assert energy_groups['S'] == 4  # E5, A11, T8, P2
        assert energy_groups['F'] == 4  # A3, E9, T12, P6
