"""Word document parser for comments, track changes, and content analysis."""

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from .models import (
    DocumentMetadata,
    DocumentStructure,
    TrackedChange,
    WordComment,
)

# Word namespace mappings
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/',
}


class WordDocumentParser:
    """Parser for Word document content, comments, and tracked changes."""
    
    def __init__(self, document_path: str):
        """Initialize parser with document path."""
        self.document_path = Path(document_path)
        self.document_root = None
        self.comments_root = None
        self.core_props_root = None
        
    def _load_docx_xml(self) -> bool:
        """Load XML content from DOCX file."""
        try:
            with zipfile.ZipFile(self.document_path, 'r') as zip_file:
                # Load main document
                if 'word/document.xml' in zip_file.namelist():
                    document_content = zip_file.read('word/document.xml')
                    self.document_root = ET.fromstring(document_content)
                
                # Load comments if they exist
                if 'word/comments.xml' in zip_file.namelist():
                    comments_content = zip_file.read('word/comments.xml')
                    self.comments_root = ET.fromstring(comments_content)
                
                # Load core properties if they exist
                if 'docProps/core.xml' in zip_file.namelist():
                    core_props_content = zip_file.read('docProps/core.xml')
                    self.core_props_root = ET.fromstring(core_props_content)
                    
                return True
        except (zipfile.BadZipFile, ET.ParseError, FileNotFoundError):
            return False
    
    def _load_xml_directory(self) -> bool:
        """Load XML content from extracted DOCX directory."""
        try:
            # Load main document
            document_file = self.document_path / "word" / "document.xml"
            if document_file.exists():
                self.document_root = ET.parse(document_file).getroot()
            
            # Load comments if they exist
            comments_file = self.document_path / "word" / "comments.xml"
            if comments_file.exists():
                self.comments_root = ET.parse(comments_file).getroot()
            
            # Load core properties if they exist
            core_props_file = self.document_path / "docProps" / "core.xml"
            if core_props_file.exists():
                self.core_props_root = ET.parse(core_props_file).getroot()
                
            return self.document_root is not None
        except (ET.ParseError, FileNotFoundError):
            return False
    
    def _load_single_xml(self) -> bool:
        """Load single document.xml file."""
        try:
            if self.document_path.name == "document.xml":
                self.document_root = ET.parse(self.document_path).getroot()
                
                # Try to find comments.xml in the same directory
                comments_file = self.document_path.parent / "comments.xml"
                if comments_file.exists():
                    self.comments_root = ET.parse(comments_file).getroot()
                    
                return True
        except (ET.ParseError, FileNotFoundError):
            return False
        return False
    
    def load(self) -> bool:
        """Load document content based on file type."""
        if self.document_path.suffix.lower() == '.docx':
            return self._load_docx_xml()
        elif self.document_path.is_dir():
            return self._load_xml_directory()
        elif self.document_path.name == "document.xml":
            return self._load_single_xml()
        return False
    
    def extract_text_from_run(self, run_elem) -> str:
        """Extract text from a Word run element."""
        text = ""
        for t_elem in run_elem.findall('.//w:t', NAMESPACES):
            if t_elem.text:
                text += t_elem.text
        return text
    
    def extract_text_from_paragraph(self, para_elem) -> str:
        """Extract text from a Word paragraph element."""
        text = ""
        for run in para_elem.findall('.//w:r', NAMESPACES):
            text += self.extract_text_from_run(run)
        return text
    
    def extract_comments(self) -> List[WordComment]:
        """Extract all comments from the document."""
        if not self.document_root or not self.comments_root:
            return []
        
        # Parse comments.xml to get comment details
        comments_data = {}
        for comment in self.comments_root.findall('.//w:comment', NAMESPACES):
            comment_id = comment.get(f"{{{NAMESPACES['w']}}}id")
            author = comment.get(f"{{{NAMESPACES['w']}}}author", "Unknown")
            date = comment.get(f"{{{NAMESPACES['w']}}}date", "")
            
            # Extract comment text
            comment_text = ""
            for para in comment.findall('.//w:p', NAMESPACES):
                comment_text += self.extract_text_from_paragraph(para) + "\\n"
            
            comments_data[comment_id] = {
                'author': author,
                'date': date,
                'text': comment_text.strip()
            }
        
        # Find comment ranges in document
        comment_ranges = self._find_comment_ranges()
        
        # Combine comment data with referenced text
        comments = []
        for comment_id, comment_data in comments_data.items():
            referenced_text, paragraph_context = comment_ranges.get(comment_id, ("", ""))
            
            comment = WordComment(
                comment_id=comment_id,
                author=comment_data['author'],
                date=comment_data['date'],
                text=comment_data['text'],
                referenced_text=referenced_text,
                paragraph_context=paragraph_context
            )
            comments.append(comment)
        
        return comments
    
    def _find_comment_ranges(self) -> Dict[str, Tuple[str, str]]:
        """Find all comment ranges and extract the text between start and end markers."""
        comment_ranges = {}
        
        # Get all paragraphs
        paragraphs = self.document_root.findall('.//w:p', NAMESPACES)
        
        for para in paragraphs:
            # Find comment range starts and ends in this paragraph
            comment_starts = {}
            comment_ends = {}
            
            # Process all elements in the paragraph to find comment markers
            for elem in para.iter():
                if elem.tag == f"{{{NAMESPACES['w']}}}commentRangeStart":
                    comment_id = elem.get(f"{{{NAMESPACES['w']}}}id")
                    if comment_id:
                        comment_starts[comment_id] = elem
                elif elem.tag == f"{{{NAMESPACES['w']}}}commentRangeEnd":
                    comment_id = elem.get(f"{{{NAMESPACES['w']}}}id")
                    if comment_id:
                        comment_ends[comment_id] = elem
            
            # For each comment range, extract text between start and end
            for comment_id in comment_starts:
                if comment_id in comment_ends:
                    start_elem = comment_starts[comment_id]
                    end_elem = comment_ends[comment_id]
                    
                    # Extract text between start and end markers
                    para_text = self.extract_text_from_paragraph(para)
                    
                    # Try to find the specific text by looking at runs between markers
                    comment_text = self._extract_comment_text_between_markers(para, start_elem, end_elem)
                    if not comment_text:
                        comment_text = para_text  # Fallback to full paragraph
                    
                    comment_ranges[comment_id] = (comment_text, para_text)
        
        return comment_ranges
    
    def _extract_comment_text_between_markers(self, para, start_marker, end_marker):
        """Extract text specifically between comment start and end markers."""
        # Get all child elements of the paragraph
        children = list(para)
        
        try:
            start_idx = children.index(start_marker)
            end_idx = children.index(end_marker)
            
            # Extract text from elements between the markers
            text = ""
            for i in range(start_idx + 1, end_idx):
                elem = children[i]
                if elem.tag == f"{{{NAMESPACES['w']}}}r":  # Run element
                    text += self.extract_text_from_run(elem)
            
            return text.strip()
        except ValueError:
            # Markers not found as direct children, fall back to regex approach
            return ""
    
    def extract_tracked_changes(self) -> List[TrackedChange]:
        """Extract tracked changes from the document."""
        if not self.document_root:
            return []
        
        changes = []
        
        # Find inserted text
        for ins in self.document_root.findall('.//w:ins', NAMESPACES):
            change_id = ins.get(f"{{{NAMESPACES['w']}}}id", "")
            author = ins.get(f"{{{NAMESPACES['w']}}}author", "Unknown")
            date = ins.get(f"{{{NAMESPACES['w']}}}date", "")
            
            # Extract inserted text
            inserted_text = ""
            for run in ins.findall('.//w:r', NAMESPACES):
                inserted_text += self.extract_text_from_run(run)
            
            change = TrackedChange(
                change_id=change_id or f"ins_{len(changes)}",
                type="insertion",
                author=author,
                date=date,
                original_text="",
                changed_text=inserted_text.strip(),
                accepted=False
            )
            changes.append(change)
        
        # Find deleted text
        for del_elem in self.document_root.findall('.//w:del', NAMESPACES):
            change_id = del_elem.get(f"{{{NAMESPACES['w']}}}id", "")
            author = del_elem.get(f"{{{NAMESPACES['w']}}}author", "Unknown")
            date = del_elem.get(f"{{{NAMESPACES['w']}}}date", "")
            
            # Extract deleted text
            deleted_text = ""
            for run in del_elem.findall('.//w:r', NAMESPACES):
                deleted_text += self.extract_text_from_run(run)
            
            change = TrackedChange(
                change_id=change_id or f"del_{len(changes)}",
                type="deletion",
                author=author,
                date=date,
                original_text=deleted_text.strip(),
                changed_text="",
                accepted=False
            )
            changes.append(change)
        
        return changes
    
    def extract_metadata(self) -> DocumentMetadata:
        """Extract document metadata."""
        metadata = DocumentMetadata(
            filename=self.document_path.name
        )
        
        # Extract from core properties if available
        if self.core_props_root:
            title_elem = self.core_props_root.find('.//dc:title', NAMESPACES)
            if title_elem is not None and title_elem.text:
                metadata.title = title_elem.text
            
            creator_elem = self.core_props_root.find('.//dc:creator', NAMESPACES)
            if creator_elem is not None and creator_elem.text:
                metadata.author = creator_elem.text
            
            subject_elem = self.core_props_root.find('.//dc:subject', NAMESPACES)
            if subject_elem is not None and subject_elem.text:
                metadata.subject = subject_elem.text
            
            created_elem = self.core_props_root.find('.//dcterms:created', NAMESPACES)
            if created_elem is not None and created_elem.text:
                metadata.created = created_elem.text
            
            modified_elem = self.core_props_root.find('.//dcterms:modified', NAMESPACES)
            if modified_elem is not None and modified_elem.text:
                metadata.modified = modified_elem.text
        
        # Count document elements
        if self.document_root:
            # Count paragraphs
            paragraphs = self.document_root.findall('.//w:p', NAMESPACES)
            metadata.paragraph_count = len(paragraphs)
            
            # Count words (rough estimate)
            total_text = ""
            for para in paragraphs:
                total_text += self.extract_text_from_paragraph(para) + " "
            
            words = total_text.strip().split()
            metadata.word_count = len([w for w in words if w.strip()])
        
        # Set format version
        if self.document_path.suffix.lower() == '.docx':
            metadata.format_version = "DOCX"
        elif self.document_path.suffix.lower() == '.doc':
            metadata.format_version = "DOC"
        else:
            metadata.format_version = "XML"
        
        return metadata
    
    def analyze_structure(self) -> DocumentStructure:
        """Analyze document structure."""
        structure = DocumentStructure()
        
        if not self.document_root:
            return structure
        
        # Find headings
        headings = []
        for para in self.document_root.findall('.//w:p', NAMESPACES):
            # Check for heading styles
            style_elem = para.find('.//w:pStyle', NAMESPACES)
            if style_elem is not None:
                style_val = style_elem.get(f"{{{NAMESPACES['w']}}}val", "")
                if "heading" in style_val.lower() or style_val.startswith("Heading"):
                    heading_text = self.extract_text_from_paragraph(para)
                    if heading_text.strip():
                        headings.append({
                            "level": style_val,
                            "text": heading_text.strip()
                        })
        
        structure.headings = headings
        structure.sections = [h["text"] for h in headings if h["text"]]
        
        # Count other elements
        structure.tables = len(self.document_root.findall('.//w:tbl', NAMESPACES))
        structure.images = len(self.document_root.findall('.//w:drawing', NAMESPACES))
        structure.hyperlinks = len(self.document_root.findall('.//w:hyperlink', NAMESPACES))
        
        return structure