#!/usr/bin/env python3
"""
Test script to verify CSV data loading functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_csv_loading():
    """Test that CSV data is loaded correctly"""
    try:
        from app.pdn_admin.admin_routes import load_user_metadata
        
        print("🔍 Testing CSV data loading...")
        
        # Load user metadata
        user_metadata = load_user_metadata()
        
        if len(user_metadata) > 0:
            print(f"✅ Successfully loaded {len(user_metadata)} user records from CSV")
            
            # Show first few records
            print("\n📋 First 3 user records:")
            for i, user in enumerate(user_metadata[:3]):
                print(f"  {i+1}. {user['email']} - PDN: {user['pdn_code']}, Voice: {user['pdn_voice_code']}, Diagnose: {user['diagnose_pdn_code']}")
            
            # Check for users with different codes (should be highlighted in red)
            different_codes = []
            for user in user_metadata:
                pdn = user['pdn_code']
                voice = user['pdn_voice_code']
                diagnose = user['diagnose_pdn_code']
                
                if (pdn != voice and voice and voice != "N/A") or \
                   (pdn != diagnose and diagnose and diagnose != "N/A") or \
                   (voice != diagnose and voice and voice != "N/A" and diagnose and diagnose != "N/A"):
                    different_codes.append(user['email'])
            
            print(f"\n🔴 Users with different PDN codes (will be highlighted in red): {len(different_codes)}")
            if different_codes:
                print("  Examples:", different_codes[:5])
            
            return True
        else:
            print("❌ No user records loaded from CSV")
            return False
            
    except Exception as e:
        print(f"❌ Error testing CSV loading: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing CSV Data Loading")
    print("=" * 40)
    
    if test_csv_loading():
        print("\n✅ CSV data loading test passed!")
    else:
        print("\n❌ CSV data loading test failed!") 