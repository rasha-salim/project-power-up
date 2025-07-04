"""
Add project planning fields migration
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

async def upgrade(engine: AsyncEngine):
    """Add project planning fields to projects table"""
    async with engine.begin() as conn:
        # Add planning_status column
        await conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN planning_status VARCHAR DEFAULT 'not_started'
        """))
        
        # Add brief_sections column for JSON data
        await conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN brief_sections JSON
        """))
        
        # Add generated_documents column for JSON data
        await conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN generated_documents JSON
        """))
        
        print("Added project planning fields: planning_status, brief_sections, generated_documents")

async def downgrade(engine: AsyncEngine):
    """Remove project planning fields from projects table"""
    async with engine.begin() as conn:
        # Remove the added columns
        await conn.execute(text("""
            ALTER TABLE projects 
            DROP COLUMN IF EXISTS planning_status
        """))
        
        await conn.execute(text("""
            ALTER TABLE projects 
            DROP COLUMN IF EXISTS brief_sections
        """))
        
        await conn.execute(text("""
            ALTER TABLE projects 
            DROP COLUMN IF EXISTS generated_documents
        """))
        
        print("Removed project planning fields")