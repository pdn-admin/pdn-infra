import unittest
from fastapi.testclient import TestClient
from app.mainOld import app

class TestAdminDashboard(unittest.TestCase):
    """Test cases for admin dashboard functionality"""
    
    def setUp(self):
        """Set up test client"""
        self.client = TestClient(app)
    
    def test_admin_dashboard_page_access(self):
        """Test admin dashboard page is accessible"""
        response = self.client.get("/admin-dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("PDN Admin Dashboard", response.text)
    
    def test_admin_login_success(self):
        """Test successful admin login"""
        response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46UGRu"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("session_token", data)
    
    def test_admin_login_failure(self):
        """Test failed admin login"""
        response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46d3Jvbmc="}
        )
        self.assertEqual(response.status_code, 401)
    
    def test_get_metadata_without_session(self):
        """Test getting metadata without valid session"""
        response = self.client.get("/admin/metadata?session_token=invalid")
        self.assertEqual(response.status_code, 401)
    
    def test_get_metadata_with_session(self):
        """Test getting metadata with valid session"""
        # First login to get session token
        login_response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46UGRu"}
        )
        session_token = login_response.json()["session_token"]
        
        # Then get metadata
        response = self.client.get(f"/admin/metadata?session_token={session_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)
    
    def test_get_user_questionnaire(self):
        """Test getting user questionnaire data"""
        # First login to get session token
        login_response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46UGRu"}
        )
        session_token = login_response.json()["session_token"]
        
        # Then get questionnaire
        response = self.client.get(f"/admin/user/questionnaire/user1@example.com?session_token={session_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user_email"], "user1@example.com")
        self.assertIn("answers", data)
    
    def test_get_user_voice(self):
        """Test getting user voice data"""
        # First login to get session token
        login_response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46UGRu"}
        )
        session_token = login_response.json()["session_token"]
        
        # Then get voice data
        response = self.client.get(f"/admin/user/voice/user1@example.com?session_token={session_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "user1@example.com")
        self.assertIn("voice_url", data)
    
    def test_update_user_diagnose(self):
        """Test updating user diagnose"""
        # First login to get session token
        login_response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46UGRu"}
        )
        session_token = login_response.json()["session_token"]
        
        # Then update diagnose
        diagnose_data = {
            "diagnose_pdn_code": "NEW-CODE",
            "diagnose_comments": "הערות חדשות"
        }
        
        response = self.client.put(
            f"/admin/user/diagnose/user1@example.com?session_token={session_token}",
            json=diagnose_data
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["user"]["diagnose_pdn_code"], "NEW-CODE")
    
    def test_logout(self):
        """Test admin logout"""
        # First login to get session token
        login_response = self.client.post(
            "/admin/login",
            headers={"Authorization": "Basic YWRtaW46UGRu"}
        )
        session_token = login_response.json()["session_token"]
        
        # Then logout
        response = self.client.get(f"/admin/logout?session_token={session_token}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

if __name__ == "__main__":
    unittest.main() 