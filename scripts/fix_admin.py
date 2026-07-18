# scripts/fix_admin.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os
import bcrypt
import psycopg2

# Get database URL from .env
db_url = os.environ.get("DATABASE_URL", "")
# Parse: postgresql://user:pass@host:port/dbname
db_url = db_url.replace("postgresql://", "")
user_pass, rest = db_url.split("@")
username, password = user_pass.split(":")
host_port, dbname = rest.split("/")
host, port = host_port.split(":") if ":" in host_port else (host_port, "5432")

# Connect directly with psycopg2 — no SQLAlchemy
conn = psycopg2.connect(
    host=host, port=port, dbname=dbname,
    user=username, password=password
)
cur = conn.cursor()

# Get admin role id
cur.execute("SELECT id FROM roles WHERE name = 'admin'")
role = cur.fetchone()
if not role:
    print("No admin role found. Run seed first.")
    sys.exit(1)
role_id = role[0]

# Delete existing admin
cur.execute("DELETE FROM users WHERE username = 'admin'")
print("Deleted old admin user")

# Create fresh bcrypt hash
pwd_hash = bcrypt.hashpw(b"Admin@12345", bcrypt.gensalt()).decode("utf-8")

# Insert new admin
import uuid
new_id = str(uuid.uuid4())
cur.execute("""
    INSERT INTO users (id, email, username, hashed_password, full_name, role_id, is_active)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
""", (new_id, "admin@railways.in", "admin", pwd_hash, "System Administrator", role_id, True))

conn.commit()
cur.close()
conn.close()

print("Admin user recreated successfully!")
print("Username: admin")
print("Password: Admin@12345")