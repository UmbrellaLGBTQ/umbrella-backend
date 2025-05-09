from app.database import engine
from app import models

def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    create_tables()