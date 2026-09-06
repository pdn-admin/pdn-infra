#!/usr/bin/env python3
"""
Simple test script to verify the Flask application structure
"""

def test_app_creation():
    """Test that the Flask app can be created successfully"""
    try:
        # Import from the root app.py file, not the app directory
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Import the create_app function directly from the app.py file
        import app as app_module
        app = app_module.create_app()
        print("✅ Flask app created successfully")
        
        # Check if blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        expected_blueprints = ['pdn_diagnose', 'pdn_admin', 'admin_api', 'audio', 'pdn_chat_ai']
        
        for expected in expected_blueprints:
            if expected in blueprint_names:
                print(f"✅ Blueprint '{expected}' registered successfully")
            else:
                print(f"❌ Blueprint '{expected}' not found")
                return False
        
        print(f"✅ All {len(expected_blueprints)} blueprints registered")
        
        # Check routes
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(rule.rule)
        
        print(f"✅ Total routes registered: {len(routes)}")
        
        # Check for key routes
        key_routes = [
            '/',
            '/pdn-diagnose/',
            '/pdn-admin/',
            '/pdn-chat-ai/'
        ]
        
        for route in key_routes:
            if route in routes:
                print(f"✅ Key route '{route}' found")
            else:
                print(f"❌ Key route '{route}' not found")
        
        # Check for admin API routes
        admin_api_routes = [
            '/pdn-admin/api/login',
            '/pdn-admin/api/metadata',
            '/pdn-admin/api/user/questionnaire/<email>',
            '/pdn-admin/api/user/voice/<email>',
            '/pdn-admin/api/audio/<path:file_path>'
        ]
        
        for route in admin_api_routes:
            if route in routes:
                print(f"✅ Admin API route '{route}' found")
            else:
                print(f"❌ Admin API route '{route}' not found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating Flask app: {e}")
        return False

def test_config():
    """Test configuration loading"""
    try:
        from config import Config, DevelopmentConfig, ProductionConfig
        print("✅ Configuration classes imported successfully")
        
        # Test config instantiation
        dev_config = DevelopmentConfig()
        prod_config = ProductionConfig()
        print("✅ Configuration classes instantiated successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Error with configuration: {e}")
        return False

def test_loggers():
    """Test logger setup"""
    try:
        # Add the current directory to the path for relative imports
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from pdn_diagnose.logger import setup_logger as setup_diagnose_logger
        from pdn_admin.logger import setup_logger as setup_admin_logger
        from pdn_chat_ai.logger import setup_logger as setup_chat_logger
        
        diagnose_logger = setup_diagnose_logger()
        admin_logger = setup_admin_logger()
        chat_logger = setup_chat_logger()
        
        print("✅ All loggers created successfully")
        
        # Test logging
        diagnose_logger.info("Test log from diagnose module")
        admin_logger.info("Test log from admin module")
        chat_logger.info("Test log from chat module")
        
        print("✅ Logging test completed")
        return True
        
    except Exception as e:
        print(f"❌ Error with loggers: {e}")
        return False

def test_admin_api():
    """Test admin API module"""
    try:
        # Add the current directory to the path for relative imports
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from pdn_admin.admin_api import admin_api_bp, get_user_metadata, verify_session
        print("✅ Admin API module imported successfully")
        
        # Test data
        user_metadata = get_user_metadata()
        if len(user_metadata) > 0:
            print(f"✅ Admin API has {len(user_metadata)} user records from CSV")
        else:
            print("❌ Admin API has no user records")
            return False
        
        # Test session verification function
        try:
            verify_session("invalid_token")
            print("❌ Session verification should have failed")
            return False
        except:
            print("✅ Session verification works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Error with admin API: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing PDN Chat Modular Flask Application")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_config),
        ("Loggers", test_loggers),
        ("Admin API", test_admin_api),
        ("Flask App", test_app_creation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} test failed")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The modular Flask application is ready.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.") 