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