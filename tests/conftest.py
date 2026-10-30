import os
from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET", "test-only-secret-that-is-not-used-in-production-0123456789")
os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
os.environ.setdefault("ENVIRONMENT", "test")
