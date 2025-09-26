#!/usr/bin/env python3
"""
Database migration script to add team management features
This script adds the new columns and tables needed for team functionality
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    db_path = "aws_manager.db"
    
    if not os.path.exists(db_path):
        print("Database file not found. Please run the application first to create the initial database.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Starting database migration for team features...")
        
        # Check if migrations are needed
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]
        
        # Add missing columns to users table
        if 'is_team_leader' not in user_columns:
            print("Adding is_team_leader column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_team_leader BOOLEAN DEFAULT 0")
        
        if 'team_id' not in user_columns:
            print("Adding team_id column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN team_id INTEGER")
        
        # Check if teams table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
        teams_table_exists = cursor.fetchone() is not None
        
        if not teams_table_exists:
            print("Creating teams table...")
            cursor.execute("""
                CREATE TABLE teams (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR UNIQUE NOT NULL,
                    description VARCHAR,
                    leader_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(leader_id) REFERENCES users (id)
                )
            """)
            
            # Create index on team name
            cursor.execute("CREATE INDEX ix_teams_name ON teams (name)")
        
        # Check if team_aws_keys association table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_aws_keys'")
        team_aws_keys_exists = cursor.fetchone() is not None
        
        if not team_aws_keys_exists:
            print("Creating team_aws_keys association table...")
            cursor.execute("""
                CREATE TABLE team_aws_keys (
                    team_id INTEGER NOT NULL,
                    aws_key_id INTEGER NOT NULL,
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (team_id, aws_key_id),
                    FOREIGN KEY(team_id) REFERENCES teams (id),
                    FOREIGN KEY(aws_key_id) REFERENCES aws_keys (id)
                )
            """)
        
        # Add foreign key constraint to users.team_id (note: SQLite doesn't support adding FK constraints to existing tables)
        # The foreign key will be enforced by the application logic
        
        conn.commit()
        print("Database migration completed successfully!")
        
        # Print summary
        cursor.execute("SELECT COUNT(*) FROM teams")
        team_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_team_leader = 1")
        team_leader_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE team_id IS NOT NULL")
        users_in_teams = cursor.fetchone()[0]
        
        print(f"\nDatabase Summary:")
        print(f"- Teams: {team_count}")
        print(f"- Team Leaders: {team_leader_count}")
        print(f"- Users in Teams: {users_in_teams}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database migration failed: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def verify_migration():
    """Verify that the migration was successful"""
    try:
        conn = sqlite3.connect("aws_manager.db")
        cursor = conn.cursor()
        
        # Check users table structure
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [column[1] for column in cursor.fetchall()]
        
        required_user_columns = ['is_team_leader', 'team_id']
        missing_columns = [col for col in required_user_columns if col not in user_columns]
        
        if missing_columns:
            print(f"Missing columns in users table: {missing_columns}")
            return False
        
        # Check if teams table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='teams'")
        if not cursor.fetchone():
            print("Teams table not found")
            return False
        
        # Check if team_aws_keys table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_aws_keys'")
        if not cursor.fetchone():
            print("team_aws_keys table not found")
            return False
        
        print("Migration verification successful!")
        return True
        
    except sqlite3.Error as e:
        print(f"Migration verification failed: {e}")
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("AWS Link Generator - Team Features Database Migration")
    print("=" * 50)
    
    success = migrate_database()
    
    if success:
        print("\nVerifying migration...")
        verify_migration()
        print("\nMigration complete! You can now start the application with team features.")
    else:
        print("\nMigration failed. Please check the error messages above.")
