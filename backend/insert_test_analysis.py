#!/usr/bin/env python3
"""
Script to insert test analysis data into the database
"""
import sqlite3
import json
from datetime import datetime

# Analysis data provided by the user
analysis_data = {
    "analysis_id": "2c3f6552-7139-4876-85fa-d8e7501b14b0",
    "project_id": "ccd058b6-869b-4720-8cdc-9e4afe2a6183",
    "version": 1,
    "technical_analysis": {
        "architecture": "RAG-based (Retrieval Augmented Generation) system with modular/customizable approach",
        "tech_stack": {
            "frontend": ["TypeScript", "React"],
            "backend": ["Python"],
            "infrastructure": ["AWS", "Vector Database (Pinecone/Weaviate)"],
            "tools": ["OpenAI APIs", "GitHub", "Notion", "Slack", "Google Drive"]
        },
        "complexity_score": 7.0,
        "maintainability_score": 8.0,
        "scalability_score": 8.0,
        "performance_score": 9.0,
        "security_score": 8.0
    },
    "risk_assessment": {
        "key_risks": [
            {
                "name": "Data Privacy and Security",
                "level": "High",
                "impact": 9,
                "probability": 6,
                "description": "Handling sensitive company data and code requires strict security measures"
            },
            {
                "name": "Integration Complexity",
                "level": "Medium",
                "impact": 7,
                "probability": 7,
                "description": "Multiple system integrations required (GitHub, Notion, Slack, Google Drive)"
            },
            {
                "name": "Performance Requirements",
                "level": "Medium",
                "impact": 8,
                "probability": 5,
                "description": "Must maintain response latency under 3 seconds"
            }
        ],
        "overall_risk_score": 6.0,
        "mitigation_strategies": [
            "Implement strict data security controls",
            "Use proven RAG frameworks",
            "Regular performance testing",
            "Phased implementation approach",
            "Comprehensive integration testing"
        ]
    },
    "project_plan": {
        "timeline": "3 months (May 15, 2025 - August 15, 2025)",
        "phases": [
            {
                "name": "Architecture & Model Selection",
                "duration": 2,
                "progress": 0,
                "description": "Select and design RAG implementation architecture"
            },
            {
                "name": "Data Integration",
                "duration": 4,
                "progress": 0,
                "description": "Integrate with existing systems and implement data synchronization"
            },
            {
                "name": "Development & Testing",
                "duration": 6,
                "progress": 0,
                "description": "Core development and testing of the solution"
            },
            {
                "name": "Deployment & Training",
                "duration": 1,
                "progress": 0,
                "description": "System deployment and user training"
            }
        ],
        "milestones": [
            {
                "name": "Architecture & Model Selection Complete",
                "date": "2025-05-30",
                "status": "upcoming",
                "description": "Finalize technical architecture and selected models"
            },
            {
                "name": "Data Integration Complete",
                "date": "2025-06-20",
                "status": "upcoming",
                "description": "All system integrations functional"
            },
            {
                "name": "Alpha Version Ready",
                "date": "2025-07-10",
                "status": "upcoming",
                "description": "Internal testing version ready"
            },
            {
                "name": "Beta Launch",
                "date": "2025-07-25",
                "status": "upcoming",
                "description": "Core team testing begins"
            },
            {
                "name": "Full Deployment",
                "date": "2025-08-15",
                "status": "upcoming",
                "description": "System fully deployed and operational"
            }
        ],
        "resource_requirements": {
            "developers": 3,
            "designers": 0,
            "qa": 1,
            "devops": 1,
            "pm": 1,
            "other": {
                "subject_matter_experts": 2
            }
        },
        "estimated_cost": 25000.0,
        "effort_distribution": [
            {"component": "Backend Development", "effort": 40},
            {"component": "Frontend Development", "effort": 25},
            {"component": "Integration", "effort": 20},
            {"component": "Testing & QA", "effort": 15}
        ]
    },
    "recommendations": [
        "Implement RAG-based solution using OpenAI APIs",
        "Use vector database (Pinecone/Weaviate) for efficient retrieval",
        "Implement strict data privacy controls",
        "Phase the implementation starting with core knowledge management",
        "Establish clear feedback mechanisms for continuous improvement",
        "Create comprehensive documentation for maintenance and scaling"
    ],
    "created_at": "2025-07-02T05:26:10.604712",
    "updated_at": "2025-07-02T05:26:10.604712"
}

def insert_analysis():
    # Connect to database
    conn = sqlite3.connect('project_powerup.db')
    cursor = conn.cursor()
    
    try:
        # Check the schema of the analyses table
        cursor.execute("PRAGMA table_info(analyses)")
        columns = cursor.fetchall()
        print("Analyses table schema:")
        for col in columns:
            print(f"  {col[1]} {col[2]}")
        
        # Convert analysis data to JSON string
        result_json = json.dumps(analysis_data)
        
        # Insert the analysis
        cursor.execute("""
            INSERT INTO analyses (id, project_id, type, result, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis_data['analysis_id'],
            analysis_data['project_id'],
            'project_analysis',  # Default type
            result_json,
            analysis_data['version'],
            analysis_data['created_at'],
            analysis_data['updated_at']
        ))
        
        conn.commit()
        print(f"Successfully inserted analysis for project {analysis_data['project_id']}")
        
        # Verify the insertion
        cursor.execute("SELECT id, project_id FROM analyses WHERE project_id = ?", 
                      (analysis_data['project_id'],))
        result = cursor.fetchone()
        if result:
            print(f"Verification: Analysis ID {result[0]} found for project {result[1]}")
        
    except Exception as e:
        print(f"Error inserting analysis: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    insert_analysis()