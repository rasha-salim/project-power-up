"""
Message formatting utilities for agent responses
"""
import re


class MessageFormatter:
    """Utility class for formatting agent messages for better readability"""
    
    @staticmethod
    def format_agent_response(text: str) -> str:
        """
        Format agent response text for better readability
        
        Args:
            text: Raw agent response text
            
        Returns:
            Formatted text with improved spacing and structure
        """
        if not text or not isinstance(text, str):
            return str(text) if text else ""
        
        # Clean up the text but preserve markdown structure
        formatted_text = MessageFormatter._clean_text(text)
        
        # Apply minimal formatting to work with ReactMarkdown
        formatted_text = MessageFormatter._format_for_markdown(formatted_text)
        
        return formatted_text.strip()
    
    @staticmethod
    def _format_for_markdown(text: str) -> str:
        """Format text specifically for ReactMarkdown consumption"""
        # Ensure proper line breaks before numbered lists
        text = re.sub(r'([^\n])\n(\d+\.)', r'\1\n\n\2', text)
        
        # Ensure proper line breaks after numbered items with detailed descriptions
        text = re.sub(r'(\d+\.\s+[^\n]+(?:\n\s*-[^\n]+)*)\n([^\n-\s])', r'\1\n\n\2', text)
        
        # Add line breaks before section headers (bold text ending with colon)
        text = re.sub(r'([^\n])\n(\*\*[^*]+\*\*:)', r'\1\n\n\2', text)
        
        # Clean up excessive line breaks (more than 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text
    
    @staticmethod
    def _ensure_proper_breaks(text: str) -> str:
        """Ensure proper line breaks for complex formatted content"""
        # Add line breaks before major sections (like risk analysis)
        text = re.sub(r'(\d+\.\s+[^-\n]+(?:\s+-\s+[^-\n]+){2,})', r'\n\1', text)
        
        # Add line breaks after complete numbered items with descriptions
        text = re.sub(r'(\d+\.\s+[^-\n]+(?:\s+-\s+[^-\n]+){2,})\s+(\d+\.)', r'\1\n\n\2', text)
        
        # Add line breaks before "Technical Implications" or similar subsections
        text = re.sub(r'(\S)\s+(Technical\s+Implications?|Description|Impact|Mitigation|Recommendations?|Additional|Summary):', r'\1\n\n\2:', text)
        
        # Add line breaks after risk categories or technical sections
        text = re.sub(r'(Level:\s+[A-Z][a-z]+)\s+(-\s+Impact)', r'\1\n\n\2', text)
        
        return text
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean up basic text issues"""
        # Remove excessive spaces within lines (but preserve line breaks)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Clean up excessive line breaks (more than 2 consecutive)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove trailing spaces from lines
        text = re.sub(r' +\n', '\n', text)
        
        # Remove trailing spaces at the end of the text
        text = re.sub(r' +$', '', text)
        
        return text.strip()
    
    @staticmethod
    def _improve_spacing(text: str) -> str:
        """Improve spacing between sections and elements"""
        # Add spacing around headers
        text = re.sub(r'(^|\n)(#{1,6}\s+[^\n]+)', r'\1\n\2\n', text)
        
        # Add spacing around bold sections that look like headers
        text = re.sub(r'(^|\n)(\*\*[^*]+\*\*:?\s*)', r'\1\n\2\n', text)
        
        # Add spacing before lists (but not if already has spacing)
        text = re.sub(r'([^\n])\n([-*+]\s+)', r'\1\n\n\2', text)
        text = re.sub(r'([^\n])\n(\d+\.\s+)', r'\1\n\n\2', text)
        
        # Add spacing after lists (but not if already has spacing)
        text = re.sub(r'([-*+]\s+[^\n]+)\n([^\n-*+\d])', r'\1\n\n\2', text)
        text = re.sub(r'(\d+\.\s+[^\n]+)\n([^\n\d])', r'\1\n\n\2', text)
        
        # Ensure paragraph breaks after numbered items with descriptions
        text = re.sub(r'(\d+\.\s+[^\n]+)\n([A-Z][^-*\d])', r'\1\n\n\2', text)
        
        return text
    
    @staticmethod
    def _format_lists(text: str) -> str:
        """Improve list formatting"""
        # Ensure consistent bullet points
        text = re.sub(r'^\s*[-*+]\s+', '- ', text, flags=re.MULTILINE)
        
        # Ensure proper spacing in numbered lists
        text = re.sub(r'^\s*(\d+)\.\s+', r'\1. ', text, flags=re.MULTILINE)
        
        return text
    
    @staticmethod
    def _format_headers(text: str) -> str:
        """Improve header formatting"""
        # Ensure headers have proper spacing
        text = re.sub(r'^(#{1,6})\s*([^\n]+)', r'\1 \2', text, flags=re.MULTILINE)
        
        # Convert bold text that looks like headers to proper headers
        text = re.sub(r'^\*\*([^*]+)\*\*:?\s*$', r'## \1', text, flags=re.MULTILINE)
        
        return text
    
    @staticmethod
    def _format_paragraphs(text: str) -> str:
        """Improve paragraph formatting and flow"""
        # Split into lines for processing
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                formatted_lines.append('')
                continue
            
            # Add proper spacing around different content types
            prev_line = lines[i-1].strip() if i > 0 else ''
            next_line = lines[i+1].strip() if i < len(lines) - 1 else ''
            
            # Add spacing before headers
            if line.startswith('#') and prev_line and not prev_line.startswith('#'):
                if formatted_lines and formatted_lines[-1] != '':
                    formatted_lines.append('')
            
            # Add spacing before numbered items if they follow descriptive text
            if re.match(r'^\d+\.', line) and prev_line and not re.match(r'^\d+\.', prev_line):
                if formatted_lines and formatted_lines[-1] != '':
                    formatted_lines.append('')
            
            formatted_lines.append(line)
            
            # Add spacing after headers
            if line.startswith('#') and next_line and not next_line.startswith('#') and next_line:
                formatted_lines.append('')
            
            # Add spacing after numbered items if followed by descriptive text
            if re.match(r'^\d+\.', line) and next_line and not re.match(r'^\d+\.', next_line) and not next_line.startswith('-'):
                formatted_lines.append('')
        
        # Join back and clean up excessive newlines
        result = '\n'.join(formatted_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result
    
    @staticmethod
    def format_structured_response(sections: dict) -> str:
        """
        Format a structured response with multiple sections
        
        Args:
            sections: Dictionary with section names as keys and content as values
            
        Returns:
            Well-formatted response text
        """
        formatted_sections = []
        
        for section_name, content in sections.items():
            if not content:
                continue
            
            # Format section header
            header = f"## {section_name}"
            
            # Format content based on type
            if isinstance(content, list):
                if content:
                    content_text = '\n'.join([f"- {item}" for item in content])
                else:
                    content_text = "No items available"
            elif isinstance(content, dict):
                content_text = '\n'.join([f"**{k}**: {v}" for k, v in content.items() if v])
            else:
                content_text = str(content)
            
            # Clean and format the content
            content_text = MessageFormatter.format_agent_response(content_text)
            
            # Combine header and content
            section_text = f"{header}\n\n{content_text}"
            formatted_sections.append(section_text)
        
        return '\n\n\n'.join(formatted_sections)
    
    @staticmethod
    def format_technical_analysis(analysis_data: dict) -> str:
        """
        Format technical analysis data in the structured format shown in the reference image
        
        Args:
            analysis_data: Dictionary containing technical analysis results
            
        Returns:
            Formatted technical analysis text
        """
        if not analysis_data:
            return "No analysis data available"
        
        sections = []
        
        # Analysis Results header
        sections.append("## Analysis Results:\n")
        
        # Technical Analysis Section
        if 'technical_analysis' in analysis_data:
            tech = analysis_data['technical_analysis']
            sections.append("### Technical Analysis")
            
            if 'architecture' in tech:
                sections.append(f"**Architecture**: {tech['architecture']}")
            
            if 'tech_stack' in tech:
                sections.append("**Tech Stack**:")
                stack = tech['tech_stack']
                if 'frontend' in stack and stack['frontend']:
                    sections.append(f"  Frontend: {', '.join(stack['frontend'])}")
                if 'backend' in stack and stack['backend']:
                    sections.append(f"  Backend: {', '.join(stack['backend'])}")
                if 'infrastructure' in stack and stack['infrastructure']:
                    sections.append(f"  Infrastructure: {', '.join(stack['infrastructure'])}")
                if 'tools' in stack and stack['tools']:
                    sections.append(f"  Tools: {', '.join(stack['tools'])}")
            
            # Scores
            scores = []
            if 'complexity_score' in tech:
                scores.append(f"Complexity: {tech['complexity_score']}/10")
            if 'maintainability_score' in tech:
                scores.append(f"Maintainability: {tech['maintainability_score']}/10")
            if 'scalability_score' in tech:
                scores.append(f"Scalability: {tech['scalability_score']}/10")
            if 'security_score' in tech:
                scores.append(f"Security: {tech['security_score']}/10")
            
            if scores:
                sections.append(f"**Scores**: {', '.join(scores)}")
        
        # Risk Assessment Section
        if 'risk_assessment' in analysis_data:
            risk = analysis_data['risk_assessment']
            sections.append("\n### Risk Assessment")
            
            if 'overall_risk_score' in risk:
                sections.append(f"**Overall Risk Score**: {risk['overall_risk_score']}/10")
            
            if 'key_risks' in risk and risk['key_risks']:
                sections.append("**Key Risks**:")
                for risk_item in risk['key_risks']:
                    risk_name = risk_item.get('name', 'Unknown Risk')
                    risk_level = risk_item.get('level', 'Unknown')
                    risk_desc = risk_item.get('description', '')
                    sections.append(f"  {risk_name} ({risk_level}) - {risk_desc}")
        
        # Project Plan Section
        if 'project_plan' in analysis_data:
            plan = analysis_data['project_plan']
            sections.append("\n### Project Plan")
            
            if 'timeline' in plan:
                sections.append(f"**Timeline**: {plan['timeline']}")
            
            if 'estimated_cost' in plan:
                cost = plan['estimated_cost']
                if isinstance(cost, (int, float)):
                    sections.append(f"**Estimated Cost**: ${cost:,.0f}")
                else:
                    sections.append(f"**Estimated Cost**: {cost}")
            
            if 'phases' in plan and plan['phases']:
                sections.append("**Phases**:")
                for phase in plan['phases']:
                    if isinstance(phase, dict):
                        phase_name = phase.get('name', 'Unknown Phase')
                        phase_duration = phase.get('duration', 'TBD')
                        phase_desc = phase.get('description', '')
                        sections.append(f"  Phase {phase_name} ({phase_duration} weeks) - {phase_desc}")
                    else:
                        sections.append(f"  {phase}")
        
        # Recommendations Section
        if 'recommendations' in analysis_data and analysis_data['recommendations']:
            sections.append("\n### Recommendations")
            for i, rec in enumerate(analysis_data['recommendations'], 1):
                sections.append(f"{i}. {rec}")
        
        return '\n'.join(sections)
    
    @staticmethod
    def format_security_analysis(analysis_data: dict) -> str:
        """
        Format security analysis data in a structured format
        
        Args:
            analysis_data: Dictionary containing security analysis results
            
        Returns:
            Formatted security analysis text
        """
        if not analysis_data:
            return "No security analysis data available"
        
        sections = []
        
        # Security Analysis Results header
        sections.append("## Security Analysis Results:\n")
        
        # Security Analysis Section
        if 'security_analysis' in analysis_data:
            security = analysis_data['security_analysis']
            sections.append("### Security Analysis")
            
            if 'overall_security_score' in security:
                sections.append(f"**Overall Security Score**: {security['overall_security_score']}/10")
            
            if 'security_posture' in security:
                sections.append(f"**Security Posture**: {security['security_posture']}")
            
            # Compliance Status
            if 'compliance_status' in security:
                compliance = security['compliance_status']
                sections.append("**Compliance Status**:")
                if 'required_standards' in compliance and compliance['required_standards']:
                    sections.append(f"  Required Standards: {', '.join(compliance['required_standards'])}")
                if 'current_compliance_level' in compliance:
                    sections.append(f"  Current Level: {compliance['current_compliance_level']}")
                if 'compliance_gaps' in compliance and compliance['compliance_gaps']:
                    sections.append(f"  Gaps: {', '.join(compliance['compliance_gaps'])}")
            
            # Authentication Analysis
            if 'authentication_analysis' in security:
                auth = security['authentication_analysis']
                sections.append("**Authentication Analysis**:")
                if 'current_mechanism' in auth:
                    sections.append(f"  Current Mechanism: {auth['current_mechanism']}")
                if 'security_level' in auth:
                    sections.append(f"  Security Level: {auth['security_level']}")
        
        # Vulnerability Assessment Section
        if 'vulnerability_assessment' in analysis_data:
            vuln = analysis_data['vulnerability_assessment']
            sections.append("\n### Vulnerability Assessment")
            
            if 'critical_vulnerabilities' in vuln and vuln['critical_vulnerabilities']:
                sections.append("**Critical Vulnerabilities**:")
                for vuln_item in vuln['critical_vulnerabilities']:
                    vuln_name = vuln_item.get('name', 'Unknown Vulnerability')
                    vuln_severity = vuln_item.get('severity', 'Unknown')
                    vuln_desc = vuln_item.get('description', '')
                    sections.append(f"  {vuln_name} ({vuln_severity}) - {vuln_desc}")
            
            if 'security_risks' in vuln and vuln['security_risks']:
                sections.append("**Security Risks**:")
                for risk_item in vuln['security_risks']:
                    risk_name = risk_item.get('name', 'Unknown Risk')
                    risk_severity = risk_item.get('severity', 'Unknown')
                    risk_category = risk_item.get('category', 'General')
                    risk_desc = risk_item.get('description', '')
                    sections.append(f"  {risk_name} ({risk_category}, {risk_severity}) - {risk_desc}")
        
        # Security Recommendations Section
        if 'security_recommendations' in analysis_data:
            recs = analysis_data['security_recommendations']
            sections.append("\n### Security Recommendations")
            
            if 'immediate_actions' in recs and recs['immediate_actions']:
                sections.append("**Immediate Actions**:")
                for action in recs['immediate_actions']:
                    sections.append(f"  • {action}")
            
            if 'short_term' in recs and recs['short_term']:
                sections.append("**Short-term (30 days)**:")
                for action in recs['short_term']:
                    sections.append(f"  • {action}")
            
            if 'long_term' in recs and recs['long_term']:
                sections.append("**Long-term (3+ months)**:")
                for action in recs['long_term']:
                    sections.append(f"  • {action}")
        
        # Security Roadmap Section
        if 'security_roadmap' in analysis_data:
            roadmap = analysis_data['security_roadmap']
            sections.append("\n### Security Implementation Roadmap")
            
            for phase_key in ['phase_1', 'phase_2', 'phase_3']:
                if phase_key in roadmap:
                    phase = roadmap[phase_key]
                    phase_name = phase.get('name', f'Phase {phase_key[-1]}')
                    phase_priority = phase.get('priority', 'Medium')
                    sections.append(f"**{phase_name}** (Priority: {phase_priority})")
                    
                    if 'actions' in phase and phase['actions']:
                        for action in phase['actions']:
                            sections.append(f"  • {action}")
                    
                    if 'estimated_effort' in phase:
                        sections.append(f"  Estimated Effort: {phase['estimated_effort']}")
        
        return '\n'.join(sections)