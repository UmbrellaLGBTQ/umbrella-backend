from app.models import Base
from app.database import engine

# Create all tables based on the SQLAlchemy models
Base.metadata.create_all(bind=engine)

print("✅ Tables created successfully!")
