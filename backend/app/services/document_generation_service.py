"""
Document Generation Service - Handles generating markdown and PDF documents from project briefs
"""
import logging
import os
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.project_service import ProjectService
from app.models.project import ProjectUpdate

logger = logging.getLogger(__name__)


class DocumentGenerationService:
    """Service for generating documents from project briefs and analysis data"""
    
    def __init__(self):
        """Initialize the document generation service"""
        self.project_service = ProjectService()
        self.output_directory = "./generated_documents"
        # Ensure output directory exists
        os.makedirs(self.output_directory, exist_ok=True)
    
    async def generate_project_brief_markdown(
        self, 
        db: AsyncSession, 
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate markdown document from project brief sections
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            Dict containing document metadata or None if failed
        """
        try:
            logger.info(f"Generating markdown document for project {project_id}")
            
            # Get project data
            project = await self.project_service.get_project(db, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                return None
            
            # Get brief sections
            brief_sections = getattr(project, 'brief_sections', {}) or {}
            if not brief_sections:
                logger.warning(f"No brief sections found for project {project_id}")
                return None
            
            # Generate markdown content
            markdown_content = self._generate_markdown_from_sections(project, brief_sections)
            
            # Save to file
            filename = f"project_brief_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            file_path = os.path.join(self.output_directory, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Create document metadata
            document_metadata = {
                "id": str(uuid.uuid4()),
                "type": "markdown",
                "filename": filename,
                "file_path": file_path,
                "file_size": os.path.getsize(file_path),
                "generated_at": datetime.now().isoformat(),
                "content_sections": len(brief_sections),
                "title": f"Project Brief - {project.name}"
            }
            
            # Update project with generated document metadata
            await self._update_project_documents(db, project_id, document_metadata)
            
            logger.info(f"Successfully generated markdown document: {filename}")
            return document_metadata
            
        except Exception as e:
            logger.error(f"Error generating markdown document for project {project_id}: {str(e)}")
            return None
    
    async def generate_analysis_report_markdown(
        self, 
        db: AsyncSession, 
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate markdown document from project analysis data
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            Dict containing document metadata or None if failed
        """
        try:
            logger.info(f"Generating analysis report for project {project_id}")
            
            # Get project data
            project = await self.project_service.get_project(db, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                return None
            
            # Get analysis insights
            insights = getattr(project, 'insights', {}) or {}
            if not insights:
                logger.warning(f"No analysis insights found for project {project_id}")
                return None
            
            # Generate markdown content
            markdown_content = self._generate_analysis_markdown(project, insights)
            
            # Save to file
            filename = f"analysis_report_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            file_path = os.path.join(self.output_directory, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Create document metadata
            document_metadata = {
                "id": str(uuid.uuid4()),
                "type": "analysis_report",
                "filename": filename,
                "file_path": file_path,
                "file_size": os.path.getsize(file_path),
                "generated_at": datetime.now().isoformat(),
                "title": f"Analysis Report - {project.name}"
            }
            
            # Update project with generated document metadata
            await self._update_project_documents(db, project_id, document_metadata)
            
            logger.info(f"Successfully generated analysis report: {filename}")
            return document_metadata
            
        except Exception as e:
            logger.error(f"Error generating analysis report for project {project_id}: {str(e)}")
            return None
    
    async def generate_comprehensive_report_markdown(
        self, 
        db: AsyncSession, 
        project_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive markdown document with both brief and analysis
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            Dict containing document metadata or None if failed
        """
        try:
            logger.info(f"Generating comprehensive report for project {project_id}")
            
            # Get project data
            project = await self.project_service.get_project(db, project_id)
            if not project:
                logger.error(f"Project {project_id} not found")
                return None
            
            # Get brief sections and analysis insights
            brief_sections = getattr(project, 'brief_sections', {}) or {}
            insights = getattr(project, 'insights', {}) or {}
            
            # Generate comprehensive markdown content
            markdown_content = self._generate_comprehensive_markdown(project, brief_sections, insights)
            
            # Save to file
            filename = f"comprehensive_report_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            file_path = os.path.join(self.output_directory, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Create document metadata
            document_metadata = {
                "id": str(uuid.uuid4()),
                "type": "comprehensive_report",
                "filename": filename,
                "file_path": file_path,
                "file_size": os.path.getsize(file_path),
                "generated_at": datetime.now().isoformat(),
                "title": f"Comprehensive Report - {project.name}"
            }
            
            # Update project with generated document metadata
            await self._update_project_documents(db, project_id, document_metadata)
            
            logger.info(f"Successfully generated comprehensive report: {filename}")
            return document_metadata
            
        except Exception as e:
            logger.error(f"Error generating comprehensive report for project {project_id}: {str(e)}")
            return None
    
    async def list_generated_documents(
        self, 
        db: AsyncSession, 
        project_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all generated documents for a project
        
        Args:
            db: Database session
            project_id: ID of the project
            
        Returns:
            List of document metadata dictionaries
        """
        try:
            project = await self.project_service.get_project(db, project_id)
            if not project:
                return []
            
            generated_documents = getattr(project, 'generated_documents', {}) or {}
            return list(generated_documents.values()) if isinstance(generated_documents, dict) else []
            
        except Exception as e:
            logger.error(f"Error listing generated documents for project {project_id}: {str(e)}")
            return []
    
    async def get_document_content(
        self, 
        db: AsyncSession, 
        project_id: str, 
        document_id: str
    ) -> Optional[str]:
        """
        Get the content of a generated document
        
        Args:
            db: Database session
            project_id: ID of the project
            document_id: ID of the document
            
        Returns:
            Document content as string or None if not found
        """
        try:
            project = await self.project_service.get_project(db, project_id)
            if not project:
                return None
            
            generated_documents = getattr(project, 'generated_documents', {}) or {}
            
            if document_id not in generated_documents:
                logger.warning(f"Document {document_id} not found for project {project_id}")
                return None
            
            document = generated_documents[document_id]
            file_path = document.get('file_path')
            
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"Document file not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error getting document content: {str(e)}")
            return None
    
    def _generate_markdown_from_sections(self, project, brief_sections: Dict[str, Any]) -> str:
        """Generate markdown content from project brief sections"""
        
        # Define section order and titles
        section_mapping = {
            "project_overview": "Project Overview",
            "project_background": "Project Background", 
            "business_case": "Business Case",
            "goals_success_criteria": "Goals & Success Criteria",
            "target_audience": "Target Audience/Users",
            "scope": "High-Level Scope",
            "requirements": "High-Level Requirements",
            "timeline": "Preliminary Timeline",
            "budget": "Preliminary Budget",
            "stakeholders": "Key Stakeholders",
            "resources": "Initial Resources",
            "next_steps": "Next Steps"
        }
        
        markdown_lines = [
            f"# Project Brief: {project.name}",
            "",
            f"**Generated on:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            f"**Project ID:** {project.id}",
            f"**Status:** {project.status.title()}",
            f"**Planning Status:** {getattr(project, 'planning_status', 'not_started').replace('_', ' ').title()}",
            "",
            "---",
            ""
        ]
        
        # Add project description if available
        if project.description:
            markdown_lines.extend([
                "## Project Description",
                "",
                project.description,
                "",
                "---",
                ""
            ])
        
        # Process brief sections in defined order
        for section_key, section_title in section_mapping.items():
            if section_key in brief_sections:
                section_data = brief_sections[section_key]
                markdown_lines.extend([
                    f"## {section_title}",
                    ""
                ])
                
                if isinstance(section_data, dict) and 'content' in section_data:
                    content = section_data['content']
                elif isinstance(section_data, str):
                    content = section_data
                else:
                    content = str(section_data)
                
                markdown_lines.extend([
                    content,
                    "",
                    "---",
                    ""
                ])
        
        # Add any additional sections not in the mapping
        for section_key, section_data in brief_sections.items():
            if section_key not in section_mapping:
                title = section_key.replace('_', ' ').title()
                markdown_lines.extend([
                    f"## {title}",
                    ""
                ])
                
                if isinstance(section_data, dict) and 'content' in section_data:
                    content = section_data['content']
                elif isinstance(section_data, str):
                    content = section_data
                else:
                    content = str(section_data)
                
                markdown_lines.extend([
                    content,
                    "",
                    "---",
                    ""
                ])
        
        # Footer
        markdown_lines.extend([
            "",
            "---",
            "",
            f"*This document was generated automatically from the Project Planning System on {datetime.now().strftime('%B %d, %Y')}.*"
        ])
        
        return "\n".join(markdown_lines)
    
    def _generate_analysis_markdown(self, project, insights: Dict[str, Any]) -> str:
        """Generate markdown content from analysis insights"""
        
        markdown_lines = [
            f"# Analysis Report: {project.name}",
            "",
            f"**Generated on:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            f"**Project ID:** {project.id}",
            f"**Status:** {project.status.title()}",
            "",
            "---",
            ""
        ]
        
        # Technical Analysis
        if 'technical_analysis' in insights:
            tech_analysis = insights['technical_analysis']
            markdown_lines.extend([
                "## Technical Analysis",
                ""
            ])
            
            if isinstance(tech_analysis, dict):
                for key, value in tech_analysis.items():
                    if key == 'architecture' and isinstance(value, list):
                        markdown_lines.extend([
                            f"### {key.replace('_', ' ').title()}",
                            ""
                        ])
                        for item in value:
                            markdown_lines.append(f"- {item}")
                        markdown_lines.append("")
                    elif key == 'complexity_score':
                        markdown_lines.extend([
                            f"### Complexity Score",
                            "",
                            f"**Score:** {value}/10",
                            ""
                        ])
                    else:
                        markdown_lines.extend([
                            f"### {key.replace('_', ' ').title()}",
                            "",
                            str(value),
                            ""
                        ])
            else:
                markdown_lines.extend([str(tech_analysis), ""])
            
            markdown_lines.extend(["---", ""])
        
        # Risk Assessment
        if 'risk_assessment' in insights:
            risk_assessment = insights['risk_assessment']
            markdown_lines.extend([
                "## Risk Assessment",
                ""
            ])
            
            if isinstance(risk_assessment, dict):
                for key, value in risk_assessment.items():
                    if key == 'risks' and isinstance(value, list):
                        markdown_lines.extend([
                            "### Identified Risks",
                            ""
                        ])
                        for risk in value:
                            if isinstance(risk, dict):
                                risk_name = risk.get('name', 'Unknown Risk')
                                risk_severity = risk.get('severity', 'Unknown')
                                risk_desc = risk.get('description', '')
                                markdown_lines.extend([
                                    f"#### {risk_name} (Severity: {risk_severity})",
                                    risk_desc,
                                    ""
                                ])
                            else:
                                markdown_lines.append(f"- {risk}")
                        markdown_lines.append("")
                    else:
                        markdown_lines.extend([
                            f"### {key.replace('_', ' ').title()}",
                            "",
                            str(value),
                            ""
                        ])
            else:
                markdown_lines.extend([str(risk_assessment), ""])
            
            markdown_lines.extend(["---", ""])
        
        # Project Plan
        if 'project_plan' in insights:
            project_plan = insights['project_plan']
            markdown_lines.extend([
                "## Project Plan",
                ""
            ])
            
            if isinstance(project_plan, dict):
                for key, value in project_plan.items():
                    if key == 'phases' and isinstance(value, list):
                        markdown_lines.extend([
                            "### Project Phases",
                            ""
                        ])
                        for i, phase in enumerate(value, 1):
                            if isinstance(phase, dict):
                                phase_name = phase.get('name', f'Phase {i}')
                                phase_duration = phase.get('duration', 'Unknown')
                                phase_desc = phase.get('description', '')
                                markdown_lines.extend([
                                    f"#### {phase_name} ({phase_duration})",
                                    phase_desc,
                                    ""
                                ])
                            else:
                                markdown_lines.append(f"{i}. {phase}")
                        markdown_lines.append("")
                    elif key == 'timeline' and isinstance(value, list):
                        markdown_lines.extend([
                            "### Timeline",
                            ""
                        ])
                        for milestone in value:
                            markdown_lines.append(f"- {milestone}")
                        markdown_lines.append("")
                    else:
                        markdown_lines.extend([
                            f"### {key.replace('_', ' ').title()}",
                            "",
                            str(value),
                            ""
                        ])
            else:
                markdown_lines.extend([str(project_plan), ""])
            
            markdown_lines.extend(["---", ""])
        
        # Recommendations
        if 'recommendations' in insights:
            recommendations = insights['recommendations']
            markdown_lines.extend([
                "## Recommendations",
                ""
            ])
            
            if isinstance(recommendations, list):
                for rec in recommendations:
                    markdown_lines.append(f"- {rec}")
                markdown_lines.append("")
            else:
                markdown_lines.extend([str(recommendations), ""])
            
            markdown_lines.extend(["---", ""])
        
        # Footer
        markdown_lines.extend([
            "",
            "---",
            "",
            f"*This analysis report was generated automatically from the Project Planning System on {datetime.now().strftime('%B %d, %Y')}.*"
        ])
        
        return "\n".join(markdown_lines)
    
    def _generate_comprehensive_markdown(self, project, brief_sections: Dict[str, Any], insights: Dict[str, Any]) -> str:
        """Generate comprehensive markdown with both brief and analysis"""
        
        markdown_lines = [
            f"# Comprehensive Project Report: {project.name}",
            "",
            f"**Generated on:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            f"**Project ID:** {project.id}",
            f"**Status:** {project.status.title()}",
            f"**Planning Status:** {getattr(project, 'planning_status', 'not_started').replace('_', ' ').title()}",
            "",
            "---",
            "",
            "# Table of Contents",
            "",
            "1. [Project Brief](#project-brief)",
            "2. [Analysis Report](#analysis-report)",
            "",
            "---",
            "",
            "# Project Brief"
        ]
        
        # Add brief content
        if brief_sections:
            brief_content = self._generate_markdown_from_sections(project, brief_sections)
            # Remove the header and metadata from brief content
            brief_lines = brief_content.split('\n')[8:]  # Skip first 8 lines (header + metadata)
            markdown_lines.extend(brief_lines)
        else:
            markdown_lines.extend([
                "",
                "*No project brief data available.*",
                ""
            ])
        
        markdown_lines.extend([
            "",
            "---",
            "",
            "# Analysis Report"
        ])
        
        # Add analysis content  
        if insights:
            analysis_content = self._generate_analysis_markdown(project, insights)
            # Remove the header and metadata from analysis content
            analysis_lines = analysis_content.split('\n')[8:]  # Skip first 8 lines (header + metadata)
            markdown_lines.extend(analysis_lines)
        else:
            markdown_lines.extend([
                "",
                "*No analysis data available.*",
                ""
            ])
        
        return "\n".join(markdown_lines)
    
    async def _update_project_documents(
        self, 
        db: AsyncSession, 
        project_id: str, 
        document_metadata: Dict[str, Any]
    ) -> None:
        """Update project with generated document metadata"""
        try:
            project = await self.project_service.get_project(db, project_id)
            if not project:
                return
            
            # Get existing generated documents
            generated_documents = getattr(project, 'generated_documents', {}) or {}
            
            # Add new document
            generated_documents[document_metadata['id']] = document_metadata
            
            # Update project
            project_update = ProjectUpdate(generated_documents=generated_documents)
            await self.project_service.update_project(db, project_id, project_update)
            
            logger.info(f"Updated project {project_id} with new document metadata")
            
        except Exception as e:
            logger.error(f"Error updating project documents: {str(e)}")


# Global instance
document_generation_service = DocumentGenerationService()