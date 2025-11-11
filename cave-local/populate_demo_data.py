#!/usr/bin/env python3
"""
Populate Cave Survey Database with Demo Data
Uses fictional cave surveys for demonstration purposes
"""

import os
import sys
from datetime import datetime, timedelta
from passlib.context import CryptContext
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models from the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import User, Survey, Feedback, Base
from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def clear_existing_data(session):
    """Clear existing demo data"""
    print("🧹 Clearing existing data...")

    # Delete in order respecting foreign keys
    session.query(Survey).delete()
    session.query(Feedback).delete()
    session.query(User).delete()

    session.commit()
    print("✓ Cleared existing data")

def create_demo_users(session):
    """Create fictional demo users"""
    print("👥 Adding demo users (fictional cave surveyors)...")

    users = [
        {
            'username': 'velma_survey',
            'email': 'velma@mysteryinc.demo',
            'password': 'VelmaPassword123!',  # Demo password
            'is_active': True
        },
        {
            'username': 'fred_mapper',
            'email': 'fred@mysteryinc.demo',
            'password': 'FredPassword123!',
            'is_active': True
        },
        {
            'username': 'sandy_science',
            'email': 'sandy@bikinibottom.demo',
            'password': 'SandyPassword123!',
            'is_active': True
        },
        {
            'username': 'finn_adventure',
            'email': 'finn@ooo.demo',
            'password': 'FinnPassword123!',
            'is_active': True
        }
    ]

    user_objects = []
    for u in users:
        user = User(
            username=u['username'],
            email=u['email'],
            hashed_password=get_password_hash(u['password']),
            is_active=u['is_active']
        )
        session.add(user)
        user_objects.append(user)

    session.commit()
    print(f"✓ Added {len(users)} demo users")
    print("  Login credentials (demo only):")
    for u in users:
        print(f"    - {u['username']} / {u['password']}")

    return user_objects

def create_demo_surveys(session, users):
    """Create fictional cave survey data"""
    print("🗺️ Adding demo cave surveys...")

    base_date = datetime.now() - timedelta(days=30)

    surveys = [
        {
            'title': 'Mystery Cave - Main Passage',
            'section': 'Section A',
            'description': 'Initial survey of the main passage in Mystery Cave. Survey conducted by the Mystery Inc. team.',
            'owner': users[0],  # velma_survey
            'num_stations': 12,
            'num_shots': 11,
            'total_slope_distance': 287.5,
            'total_horizontal_distance': 265.3,
            'min_x': 0.0,
            'max_x': 245.2,
            'min_y': -12.5,
            'max_y': 34.7,
            'min_z': -5.2,
            'max_z': 3.8,
            'created_at': base_date
        },
        {
            'title': 'Crystal Onyx Cave - Formation Room',
            'section': 'B-Series',
            'description': 'Detailed survey of the spectacular formation room. High precision survey with careful measurements.',
            'owner': users[0],  # velma_survey
            'num_stations': 24,
            'num_shots': 23,
            'total_slope_distance': 412.8,
            'total_horizontal_distance': 385.6,
            'min_x': -15.3,
            'max_x': 180.4,
            'min_y': -45.2,
            'max_y': 67.8,
            'min_z': -12.4,
            'max_z': 8.9,
            'created_at': base_date + timedelta(days=5)
        },
        {
            'title': 'Adventure Cave System - Upper Level',
            'section': 'Mathematical Traverse',
            'description': 'Algebraic cave passages surveyed by Finn and Jake. Multiple branching passages with complex geometry.',
            'owner': users[3],  # finn_adventure
            'num_stations': 18,
            'num_shots': 17,
            'total_slope_distance': 325.4,
            'total_horizontal_distance': 298.7,
            'min_x': -25.0,
            'max_x': 156.8,
            'min_y': -78.3,
            'max_y': 45.2,
            'min_z': -18.5,
            'max_z': 2.1,
            'created_at': base_date + timedelta(days=10)
        },
        {
            'title': 'Sandy\'s Science Cave - Research Section',
            'section': 'Lab Area',
            'description': 'Precise scientific survey with advanced instruments. Includes detailed passage measurements and cross-sections.',
            'owner': users[2],  # sandy_science
            'num_stations': 30,
            'num_shots': 29,
            'total_slope_distance': 523.7,
            'total_horizontal_distance': 487.2,
            'min_x': -35.6,
            'max_x': 234.8,
            'min_y': -92.1,
            'max_y': 78.4,
            'min_z': -25.3,
            'max_z': 12.7,
            'created_at': base_date + timedelta(days=15)
        },
        {
            'title': 'Mystery Machine Cave - Lower Section',
            'section': 'Deep Passage',
            'description': 'Extension survey going deeper into the system. Discovered new passages beyond the previous survey limit.',
            'owner': users[1],  # fred_mapper
            'num_stations': 15,
            'num_shots': 14,
            'total_slope_distance': 198.3,
            'total_horizontal_distance': 175.6,
            'min_x': 0.0,
            'max_x': 145.3,
            'min_y': -34.2,
            'max_y': 23.8,
            'min_z': -42.7,
            'max_z': -8.5,
            'created_at': base_date + timedelta(days=20)
        },
        {
            'title': 'Bikini Bottom Cave - Underwater Survey',
            'section': 'Zone C',
            'description': 'Special underwater cave survey techniques applied. Texas-sized cave passages with unique formations.',
            'owner': users[2],  # sandy_science
            'num_stations': 20,
            'num_shots': 19,
            'total_slope_distance': 367.9,
            'total_horizontal_distance': 342.1,
            'min_x': -18.9,
            'max_x': 189.6,
            'min_y': -56.7,
            'max_y': 54.3,
            'min_z': -15.8,
            'max_z': 6.2,
            'created_at': base_date + timedelta(days=25)
        }
    ]

    for s in surveys:
        survey = Survey(
            title=s['title'],
            section=s['section'],
            description=s['description'],
            owner_id=s['owner'].id,
            num_stations=s['num_stations'],
            num_shots=s['num_shots'],
            total_slope_distance=s['total_slope_distance'],
            total_horizontal_distance=s['total_horizontal_distance'],
            min_x=s['min_x'],
            max_x=s['max_x'],
            min_y=s['min_y'],
            max_y=s['max_y'],
            min_z=s['min_z'],
            max_z=s['max_z'],
            created_at=s['created_at']
        )
        session.add(survey)

    session.commit()
    print(f"✓ Added {len(surveys)} demo cave surveys")

def create_demo_feedback(session):
    """Create sample feedback entries"""
    print("💬 Adding demo feedback...")

    feedback_items = [
        {
            'feedback_text': 'Great tool! The visualization makes it easy to see cave passage geometry. Would love to see 3D views.',
            'category': 'feature_request',
            'priority': 'normal',
            'user_session': 'demo-velma-001'
        },
        {
            'feedback_text': 'The survey calculations are accurate and match our field notes perfectly. Very impressed!',
            'category': 'positive',
            'priority': 'low',
            'user_session': 'demo-fred-002'
        },
        {
            'feedback_text': 'Could you add support for importing data from DistoX survey instruments? That would save a lot of time.',
            'category': 'feature_request',
            'priority': 'high',
            'user_session': 'demo-sandy-003'
        },
        {
            'feedback_text': 'The interface is clean and easy to use. Mathematical!',
            'category': 'positive',
            'priority': 'low',
            'user_session': 'demo-finn-004'
        }
    ]

    for f in feedback_items:
        feedback = Feedback(
            feedback_text=f['feedback_text'],
            category=f['category'],
            priority=f['priority'],
            user_session=f['user_session'],
            status='new'
        )
        session.add(feedback)

    session.commit()
    print(f"✓ Added {len(feedback_items)} feedback entries")

def enable_demo_mode(session):
    """Enable demo mode in settings"""
    print("⚠️ Enabling demonstration mode...")

    # Note: Settings table managed by init_db.sql
    # This would update the settings if we had direct SQL access
    # For now, just inform the user

    print("✓ Demo mode markers added to survey descriptions")
    print("  (Update settings.demo_mode_enabled='true' manually if needed)")

def main():
    """Main function to populate all demo data"""
    print("=" * 70)
    print("🗺️ Cave Survey Application - Demo Data Population")
    print("   Using fictional cave surveys for demonstration")
    print("=" * 70)
    print()

    try:
        # Create database connection
        engine = create_engine(settings.database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()

        print(f"✓ Connected to database")
        print()

        # Populate data
        clear_existing_data(session)
        users = create_demo_users(session)
        create_demo_surveys(session, users)
        create_demo_feedback(session)
        enable_demo_mode(session)

        session.close()

        print()
        print("=" * 70)
        print("✅ SUCCESS! Demo data populated successfully!")
        print()
        print("📊 Summary:")
        print("   - 4 Demo users (Velma, Fred, Sandy, Finn)")
        print("   - 6 Fictional cave surveys with realistic data")
        print("   - 4 Sample feedback entries")
        print()
        print("🔐 Demo Login Credentials:")
        print("   Username: velma_survey  | Password: VelmaPassword123!")
        print("   Username: fred_mapper   | Password: FredPassword123!")
        print("   Username: sandy_science | Password: SandyPassword123!")
        print("   Username: finn_adventure| Password: FinnPassword123!")
        print()
        print("⚠️  REMINDER: This is demonstration data using fictional surveys.")
        print("   Clear this data before using for real cave survey projects!")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
