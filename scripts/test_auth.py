# scripts/test_auth.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.security import verify_password
from app.repositories.user_repository import UserRepository

print("Testing authentication components...")

with SessionLocal() as db:
    # Step 1: Direct DB check
    r = db.execute(text("SELECT username, hashed_password, is_active FROM users WHERE username='admin'")).fetchone()
    if not r:
        print("FAIL: Admin user not found in DB")
        sys.exit(1)
    print(f"PASS: Found user '{r[0]}' | active={r[2]}")

    # Step 2: Repository check
    repo = UserRepository(db)
    user = repo.get_by_username("admin")
    if not user:
        print("FAIL: UserRepository.get_by_username returned None")
        sys.exit(1)
    print(f"PASS: Repository found user | role={user.role}")

    # Step 3: Password check
    ok = verify_password("Admin@12345", user.hashed_password)
    print(f"{'PASS' if ok else 'FAIL'}: verify_password = {ok}")

    # Step 4: Full authenticate_user
    from app.services.auth_service import authenticate_user
    result = authenticate_user(db, "admin", "Admin@12345")
    print(f"{'PASS' if result else 'FAIL'}: authenticate_user = {result}")

    if result:
        # Step 5: Token creation
        from app.services.auth_service import create_tokens_for_user
        tokens = create_tokens_for_user(result)
        print(f"PASS: Tokens created | keys={list(tokens.keys())}")
        print("\nAll checks passed! Login should work.")
    else:
        print("\nFAIL: authenticate_user returned None — check auth_service.py")