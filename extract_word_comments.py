#!/usr/bin/env python3
"""
Extract Word document comments and their referenced text from DOCX XML files.
"""

import xml.etree.ElementTree as ET
import re
from typing import Dict, List, Tuple
import sys

# Word namespace mappings
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
}

def extract_text_from_run(run_elem) -> str:
    """Extract text from a Word run element."""
    text = ""
    for t_elem in run_elem.findall('.//w:t', NAMESPACES):
        if t_elem.text:
            text += t_elem.text
    return text

def extract_text_from_paragraph(para_elem) -> str:
    """Extract text from a Word paragraph element."""
    text = ""
    for run in para_elem.findall('.//w:r', NAMESPACES):
        text += extract_text_from_run(run)
    return text

def find_comment_ranges(document_root) -> Dict[str, Tuple[str, str]]:
    """Find all comment ranges and extract the text between start and end markers."""
    comment_ranges = {}
    
    # Get all paragraphs
    paragraphs = document_root.findall('.//w:p', NAMESPACES)
    
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
                # This is a simplified approach - we'll get the whole paragraph text
                # A more sophisticated approach would track exact positions
                para_text = extract_text_from_paragraph(para)
                
                # Try to find the specific text by looking at runs between markers
                comment_text = extract_comment_text_between_markers(para, start_elem, end_elem)
                if not comment_text:
                    comment_text = para_text  # Fallback to full paragraph
                
                comment_ranges[comment_id] = (comment_text, para_text)
    
    return comment_ranges

def extract_comment_text_between_markers(para, start_marker, end_marker):
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
                text += extract_text_from_run(elem)
        
        return text.strip()
    except ValueError:
        # Markers not found as direct children, fall back to regex approach
        return ""

def parse_comments_xml(comments_file) -> Dict[str, Dict]:
    """Parse the comments.xml file to get comment details."""
    tree = ET.parse(comments_file)
    root = tree.getroot()
    
    comments = {}
    for comment in root.findall('.//w:comment', NAMESPACES):
        comment_id = comment.get(f"{{{NAMESPACES['w']}}}id")
        author = comment.get(f"{{{NAMESPACES['w']}}}author")
        date = comment.get(f"{{{NAMESPACES['w']}}}date")
        
        # Extract comment text
        comment_text = ""
        for para in comment.findall('.//w:p', NAMESPACES):
            comment_text += extract_text_from_paragraph(para) + "\n"
        
        comments[comment_id] = {
            'author': author,
            'date': date,
            'text': comment_text.strip()
        }
    
    return comments

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_word_comments.py <docx_directory>")
        print("Where <docx_directory> is the unzipped DOCX file directory")
        sys.exit(1)
    
    docx_dir = sys.argv[1]
    document_xml = f"{docx_dir}/word/document.xml"
    comments_xml = f"{docx_dir}/word/comments.xml"
    
    try:
        # Parse document to find comment ranges
        doc_tree = ET.parse(document_xml)
        doc_root = doc_tree.getroot()
        comment_ranges = find_comment_ranges(doc_root)
        
        # Parse comments to get comment details
        comments = parse_comments_xml(comments_xml)
        
        # Combine and display results
        print("WORD DOCUMENT COMMENTS ANALYSIS")
        print("=" * 50)
        print()
        
        for comment_id in sorted(comments.keys(), key=lambda x: int(x)):
            comment_data = comments[comment_id]
            print(f"COMMENT {comment_id} ({comment_data['author']}) - {comment_data['date']}")
            print("-" * 40)
            print(f"Comment: {comment_data['text']}")
            print()
            
            if comment_id in comment_ranges:
                referenced_text, paragraph_context = comment_ranges[comment_id]
                print(f"Referenced text: '{referenced_text}'")
                if referenced_text != paragraph_context:
                    print(f"Full paragraph: '{paragraph_context}'")
            else:
                print("Referenced text: [Could not extract]")
            
            print()
            print("=" * 50)
            print()
    
    except FileNotFoundError as e:
        print(f"Error: Could not find file {e.filename}")
        print("Make sure you've unzipped the DOCX file and provided the correct directory path")
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")

if __name__ == "__main__":
    main()