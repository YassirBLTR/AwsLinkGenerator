"""
Migration script to update BucketHistory table for user/key deletion preservation
"""
import sqlite3
from models import User, AWSKey, BucketHistory
from database import SessionLocal

def migrate_bucket_history():
    """Update BucketHistory table to preserve history when users/keys are deleted"""
    
    # Connect to SQLite database directly for schema changes
    conn = sqlite3.connect('aws_manager.db')
    cursor = conn.cursor()
    
    try:
        print("Starting BucketHistory table migration...")
        
        # Step 1: Add new columns for storing user/key names
        try:
            cursor.execute("ALTER TABLE bucket_history ADD COLUMN user_name TEXT")
            print("+ Added user_name column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("+ user_name column already exists")
            else:
                raise
        
        try:
            cursor.execute("ALTER TABLE bucket_history ADD COLUMN aws_key_name TEXT")
            print("+ Added aws_key_name column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("+ aws_key_name column already exists")
            else:
                raise
        
        # Step 2: Populate the new columns with current user/key names
        db = SessionLocal()
        try:
            # Get all history records that have valid user/key relationships
            history_records = db.query(BucketHistory).all()
            
            for record in history_records:
                updated = False
                
                # Store user name if user exists and user_name is not set
                if record.user and not record.user_name:
                    cursor.execute(
                        "UPDATE bucket_history SET user_name = ? WHERE id = ?",
                        (record.user.username, record.id)
                    )
                    updated = True
                
                # Store AWS key name if key exists and aws_key_name is not set
                if record.aws_key and not record.aws_key_name:
                    cursor.execute(
                        "UPDATE bucket_history SET aws_key_name = ? WHERE id = ?",
                        (record.aws_key.name, record.id)
                    )
                    updated = True
                
                if updated:
                    print(f"+ Updated history record {record.id}")
            
            print("+ Populated user_name and aws_key_name columns")
            
        finally:
            db.close()
        
        # Step 3: Create new table with proper foreign key constraints
        print("Creating new table with SET NULL constraints...")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bucket_history_new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                aws_key_id INTEGER REFERENCES aws_keys(id) ON DELETE SET NULL,
                bucket_name TEXT NOT NULL,
                region TEXT NOT NULL,
                image_url TEXT,
                html_url TEXT,
                creation_status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_name TEXT,
                aws_key_name TEXT
            )
        """)
        
        # Step 4: Copy data from old table to new table
        cursor.execute("""
            INSERT INTO bucket_history_new 
            SELECT id, user_id, aws_key_id, bucket_name, region, image_url, html_url, 
                   creation_status, error_message, created_at, user_name, aws_key_name
            FROM bucket_history
        """)
        
        # Step 5: Drop old table and rename new table
        cursor.execute("DROP TABLE bucket_history")
        cursor.execute("ALTER TABLE bucket_history_new RENAME TO bucket_history")
        
        # Commit all changes
        conn.commit()
        print("+ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"- Migration failed: {str(e)}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_bucket_history()
