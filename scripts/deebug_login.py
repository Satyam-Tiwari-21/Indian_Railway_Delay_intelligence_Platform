# scripts/debug_login.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import bcrypt
from sqlalchemy import text
from app.core.database import SessionLocal

with SessionLocal() as db:
    # Check if admin exists
    result = db.execute(text("SELECT id, username, hashed_password, is_active FROM users WHERE username = 'admin'")).fetchone()
    
    if not result:
        print("❌ Admin user does NOT exist in database")
        print("   Run: python scripts/seed.py")
    else:
        print(f"✅ Admin user found")
        print(f"   ID: {result[0]}")
        print(f"   Username: {result[1]}")
        print(f"   Is Active: {result[3]}")
        print(f"   Hash preview: {result[2][:30]}...")
        
        # Test password verification
        password = "Admin@12345"
        stored_hash = result[2]
        
        try:
            match = bcrypt.checkpw(
                password.encode("utf-8"),
                stored_hash.encode("utf-8")
            )
            print(f"\n{'✅' if match else '❌'} bcrypt.checkpw result: {match}")
        except Exception as e:
            print(f"\n❌ bcrypt.checkpw error: {e}")
        
        # Test via API auth service
        try:
            from app.core.security import verify_password
            result2 = verify_password(password, stored_hash)
            print(f"{'✅' if result2 else '❌'} verify_password result: {result2}")
        except Exception as e:
            print(f"❌ verify_password error: {e}")