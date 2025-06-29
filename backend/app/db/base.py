"""
Base module for SQLAlchemy models
Provides a single Base class for all models to inherit from
"""
from sqlalchemy.ext.declarative import declarative_base

# Create a single Base class for all models
Base = declarative_base()
