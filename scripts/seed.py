"""
scripts/seed.py
Seeds the database with default roles and admin user.
Run after: alembic upgrade head
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file
from dotenv import load_dotenv
load_dotenv()

from app.core.database import SessionLocal, check_db_connection
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def seed_roles(db):
    from app.models.db.user import Role
    from app.core.rbac import ROLE_PERMISSIONS

    for role_name, permissions in ROLE_PERMISSIONS.items():
        existing = db.query(Role).filter(Role.name == role_name).first()
        if existing is None:
            db.add(Role(
                name=role_name,
                description=f"Default {role_name} role",
                permissions=permissions,
            ))
            print(f"  Created role: {role_name}")
        else:
            print(f"  Role already exists: {role_name}")
    db.flush()


def seed_admin(db):
    from app.models.db.user import User, Role
    from app.core.security import get_password_hash

    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        print("  ERROR: Run seed_roles() first")
        return

    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("  Admin user already exists — skipping")
        return

    import uuid
    db.add(User(
        id=str(uuid.uuid4()),
        email="admin@railways.in",
        username="admin",
        hashed_password=get_password_hash("Admin@12345"),
        full_name="System Administrator",
        role_id=admin_role.id,
        is_active=True,
    ))
    db.flush()
    print("  Admin user created")
    print("  Username: admin")
    print("  Password: Admin@12345")
    print("  ⚠️  Change the password after first login!")


def main():
    print("\nChecking database connection...")
    status = check_db_connection()
    if status["status"] != "healthy":
        print(f"❌ Database not reachable: {status.get('error')}")
        print("   Make sure PostgreSQL is running and DATABASE_URL is correct in .env")
        sys.exit(1)
    print("  ✅ Database connected\n")

    with SessionLocal() as db:
        try:
            print("Seeding roles...")
            seed_roles(db)
            print("\nSeeding admin user...")
            seed_admin(db)
            db.commit()
            print("\n✅ Seed completed successfully!")
            print("\nNext step: uvicorn app.main:app --reload --port 8000")
        except Exception as e:
            db.rollback()
            print(f"\n❌ Seed failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()