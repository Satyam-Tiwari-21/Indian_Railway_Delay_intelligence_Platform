# scripts/fix_admin.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import bcrypt
from sqlalchemy import text
from app.core.database import SessionLocal

with SessionLocal() as db:
    # Delete old admin user
    db.execute(text("DELETE FROM users WHERE username = 'admin'"))
    db.commit()
    print("Old admin user deleted")

print("Now run: python scripts/seed.py")