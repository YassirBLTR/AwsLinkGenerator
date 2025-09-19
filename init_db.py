#!/usr/bin/env python3
"""
Database initialization script for AWS S3 Manager
Creates the initial admin user and sets up the database tables.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import Base, SQLALCHEMY_DATABASE_URL
from models import User, AWSKey
from passlib.context import CryptContext

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def init_database():
    # Create engine
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if new columns exist, if not add them
        try:
            # Try to query the new columns
            db.execute(text("SELECT status, last_checked FROM aws_keys LIMIT 1"))
            print("ℹ️  Database schema is up to date")
        except Exception:
            # Add new columns if they don't exist
            print("🔄 Updating database schema...")
            try:
                db.execute(text("ALTER TABLE aws_keys ADD COLUMN status TEXT DEFAULT 'unchecked'"))
                db.execute(text("ALTER TABLE aws_keys ADD COLUMN last_checked DATETIME"))
                db.commit()
                print("✅ Added status and last_checked columns to aws_keys table")
            except Exception as e:
                print(f"⚠️  Schema update error (may be normal if columns already exist): {e}")
                db.rollback()
        
        # Check if admin user exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            # Create default admin user
            admin_user = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                is_admin=True
            )
            db.add(admin_user)
            db.commit()
            print("✅ Created default admin user (username: admin, password: admin123)")
        else:
            print("ℹ️  Admin user already exists")
        
        # Check if AWS keys exist
        existing_keys = db.query(AWSKey).count()
        if existing_keys == 0:
            # Add sample AWS keys
            sample_keys = [
                AWSKey(
                    name="AWS Account 1",
                    access_key="AKIAIOSFODNN7EXAMPLE",
                    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    user_id=None,
                    status="unchecked"
                ),
                AWSKey(
                    name="AWS Account 2", 
                    access_key="AKIAI44QH8DHBEXAMPLE",
                    secret_key="je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY",
                    user_id=None,
                    status="unchecked"
                ),
                AWSKey(
                    name="AWS Account 3",
                    access_key="AKIAIOSFODNN7EXAMPLE",
                    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    user_id=None,
                    status="unchecked"
                )
            ]
            
            for key in sample_keys:
                db.add(key)
            
            db.commit()
            print(f"✅ Created {len(sample_keys)} sample AWS keys")
        else:
            print(f"ℹ️  {existing_keys} AWS keys already exist")
            
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("🎉 Database initialization completed!")
    print("\n📋 Next steps:")
    print("1. Run: python main.py")
    print("2. Open: http://localhost:8000")
    print("3. Login with admin/admin123")
    print("4. Create users and assign AWS keys")

if __name__ == "__main__":
    init_database()
