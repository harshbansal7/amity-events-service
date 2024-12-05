from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

# MongoDB connection
client = MongoClient(os.getenv('MONGO_URI'))
db = client.get_default_database()

def generate_dummy_data():
    """Generate random data for user fields"""
    branches = ['CSE', 'IT', 'ECE', 'EEE', 'MAE', 'ICE', 'BT']
    
    return {
        'branch': random.choice(branches),
        'year': random.randint(1, 4),
        'name': 'Student',  # Default name
        'email': "dummy@dummy.com"  # Will be generated based on enrollment number
    }

def migrate_users():
    """Update existing users with new required fields"""
    users_collection = db.users
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    print("Starting user migration...")
    
    for user in users_collection.find():
        try:
            # Skip if user already has all required fields
            if all(field in user for field in ['name', 'email', 'branch', 'year']):
                skipped_count += 1
                continue
                
            # Generate dummy data
            dummy_data = generate_dummy_data()
            
            enrollment = user['enrollment_number']
            dummy_data['name'] = f"Student {enrollment}"
            
            # Update user document
            result = users_collection.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'name': dummy_data['name'],
                        'email': dummy_data['email'],
                        'branch': dummy_data['branch'],
                        'year': dummy_data['year'],
                    }
                }
            )
            
            if result.modified_count:
                updated_count += 1
                print(f"Updated user: {enrollment}")
            else:
                error_count += 1
                print(f"Failed to update user: {enrollment}")
                
        except Exception as e:
            error_count += 1
            print(f"Error processing user {user.get('enrollment_number', 'Unknown')}: {str(e)}")
    
    print("\nMigration Summary:")
    print(f"Total users processed: {updated_count + skipped_count + error_count}")
    print(f"Users updated: {updated_count}")
    print(f"Users skipped (already had data): {skipped_count}")
    print(f"Errors encountered: {error_count}")

def rollback_migration():
    """Remove added fields in case of issues"""
    users_collection = db.users
    
    print("Rolling back migration...")
    
    result = users_collection.update_many(
        {'migrated_at': {'$exists': True}},
        {
            '$unset': {
                'name': '',
                'email': '',
                'branch': '',
                'year': '',
                'migrated_at': ''
            }
        }
    )
    
    print(f"Rolled back {result.modified_count} users")

if __name__ == "__main__":
    while True:
        print("\nUser Migration Script")
        print("1. Run migration")
        print("2. Rollback migration")
        print("3. Exit")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            migrate_users()
        elif choice == '2':
            confirm = input("Are you sure you want to rollback? This will remove all migrated data! (y/n): ")
            if confirm.lower() == 'y':
                rollback_migration()
        elif choice == '3':
            break
        else:
            print("Invalid choice!") 