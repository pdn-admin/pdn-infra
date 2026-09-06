#!/usr/bin/env python3
"""
Test script to verify CSV functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_csv_functionality():
    """Test CSV functionality"""
    try:
        from app.utils.csv_metadata_handler import UserMetadataHandler
        
        print("🔍 Testing CSV functionality...")
        
        # Create CSV handler
        csv_handler = UserMetadataHandler()
        
        # Test 1: Append new user
        print("\n📝 Test 1: Appending new user to CSV...")
        test_user_data = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '123-456-7890'
        }
        
        success = csv_handler.append_user_metadata(test_user_data)
        if success:
            print("✅ Successfully appended new user to CSV")
        else:
            print("❌ Failed to append new user to CSV")
            return False
        
        # Test 2: Update PDN code
        print("\n📝 Test 2: Updating PDN code...")
        success = csv_handler.update_pdn_code('test@example.com', 'E5')
        if success:
            print("✅ Successfully updated PDN code")
        else:
            print("❌ Failed to update PDN code")
            return False
        
        # Test 3: Update voice code
        print("\n📝 Test 3: Updating voice code...")
        success = csv_handler.update_voice_code('test@example.com', 'V3')
        if success:
            print("✅ Successfully updated voice code")
        else:
            print("❌ Failed to update voice code")
            return False
        
        # Test 4: Update diagnose code
        print("\n📝 Test 4: Updating diagnose code...")
        success = csv_handler.update_diagnose_code('test@example.com', 'E5', 'Test diagnosis comments')
        if success:
            print("✅ Successfully updated diagnose code")
        else:
            print("❌ Failed to update diagnose code")
            return False
        
        # Test 5: Read all metadata
        print("\n📝 Test 5: Reading all metadata...")
        all_data = csv_handler.read_all_metadata()
        print(f"✅ Successfully read {len(all_data)} records from CSV")
        
        # Find our test user
        test_user = None
        for user in all_data:
            if user.get('Email', '').strip() == 'test@example.com':
                test_user = user
                break
        
        if test_user:
            print("✅ Found test user in CSV:")
            print(f"   Email: {test_user.get('Email')}")
            print(f"   Date: {test_user.get('Date')}")
            print(f"   PDN Code: {test_user.get('PDN Code')}")
            print(f"   Voice Code: {test_user.get('PDN Voice Code')}")
            print(f"   Diagnose Code: {test_user.get('Diagnose PDN Code')}")
            print(f"   Comments: {test_user.get('Diagnose Comments')}")
        else:
            print("❌ Test user not found in CSV")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing CSV functionality: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing CSV Functionality")
    print("=" * 40)
    
    if test_csv_functionality():
        print("\n✅ All CSV functionality tests passed!")
    else:
        print("\n❌ Some CSV functionality tests failed!") 