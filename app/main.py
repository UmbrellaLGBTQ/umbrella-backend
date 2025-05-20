from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from .models import Base
from .database import engine
from .database import Base, engine, SessionLocal
from app import models
import uvicorn
from .routes import profiles, connections, posts, chats, search, block


# Create tables on startup (dev only)
Base.metadata.create_all(bind=engine)

# Import routes
from .routes import signup, login, oauth, forget_password, theme, country_code

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Umbrella Backend API",
    description="Authentication and profile management API",
    version="1.0.0"
)
 

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(country_code.router)  
app.include_router(signup.router)
app.include_router(theme.router)
app.include_router(login.router)
app.include_router(oauth.router)
app.include_router(forget_password.router)
app.include_router(profiles.router)  # New profile router
app.include_router(connections.router)  # New connections router
app.include_router(posts.router)
app.include_router(chats.router)
app.include_router(search.router)
app.include_router(block.router)

@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": "Welcome to Umbrella Backend API",
        "docs": "/docs",
        "health": "OK"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}
