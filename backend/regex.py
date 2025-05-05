import os
import re
import yaml
import json
from typing import Dict, List, Any, Generator, Optional
import PyPDF2

class DocumentProcessor:
    def __init__(self, config_path: str = "config.yaml", chunk_size: int = 1000):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.chunk_size = chunk_size

    def is_semantic_boundary(self, text: str) -> bool:
        """Check if the text contains a semantic boundary"""
        boundary_patterns = [
            r'\n\s*\n',  # Multiple newlines
            r'Table\s+\d+\.',  # Table start
            r'Figure\s+\d+\.',  # Figure start
            r'^\s*\d+\.\d+\.\d+\s+',  # Subsection
            r'^\s*\d+\.\d+\s+',  # Section
            r'^\s*Chapter\s+\d+',  # Chapter
            r'^\s*References\s*$',  # References section
            r'^\s*Bibliography\s*$',  # Bibliography
            r'^\s*Appendix\s+[A-Z]\s*$',  # Appendix
        ]
        
        for pattern in boundary_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False

    def extract_text_from_pdf(self, file_path: str) -> Generator[str, None, None]:
        """Extract text from PDF in semantic chunks"""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            current_chunk = ""
            
            for page in reader.pages:
                page_text = page.extract_text()
                lines = page_text.split('\n')
                
                for line in lines:
                    current_chunk += line + '\n'
                    
                    if self.is_semantic_boundary(current_chunk):
                        if current_chunk.strip():
                            yield current_chunk.strip()
                        current_chunk = ""
                    elif len(current_chunk) >= self.chunk_size:
                        lines_in_chunk = current_chunk.split('\n')
                        for i in range(min(5, len(lines_in_chunk))):
                            if self.is_semantic_boundary('\n'.join(lines_in_chunk[:-i])):
                                yield '\n'.join(lines_in_chunk[:-i]).strip()
                                current_chunk = '\n'.join(lines_in_chunk[-i:])
                                break
                        else:
                            yield current_chunk.strip()
                            current_chunk = ""
            
            if current_chunk.strip():
                yield current_chunk.strip()

    def clean_text(self, text: str) -> str:
        """Clean up text by removing special characters and extra whitespace"""
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = text.replace('\u2013', '-').replace('\u2014', '-')
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def process_document(self, file_path: str) -> Dict[str, Any]:
        # Extract text chunks
        text_chunks = list(self.extract_text_from_pdf(file_path))
        
        result = {
            "student_info": {},
            "semesters": [],
            "cumulative_gpa": 0.0
        }
        
        current_semester = None
        
        for chunk in text_chunks:
            lines = chunk.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                    
                # Check for student info
                if line.startswith("Name:"):
                    result["student_info"]["name"] = line.split("Name:")[1].strip()
                    i += 1
                    continue
                elif line.startswith("Student ID:"):
                    result["student_info"]["id"] = line.split("Student ID:")[1].strip()
                    i += 1
                    continue
                
                # Check for semester header (e.g., "2023 Fall")
                semester_match = re.match(r'^(\d{4})\s+(Spring|Summer|Fall)$', line)
                if semester_match:
                    if current_semester:
                        result["semesters"].append(current_semester)
                    current_semester = {
                        "year": int(semester_match.group(1)),
                        "semester": semester_match.group(2),
                        "courses": [],
                        "gpa": 0.0
                    }
                    i += 1
                    continue
                
                # Check for course entry
                if current_semester and re.match(r'^[A-Z]{3}\d{4}', line):
                    parts = line.split()
                    # Add space between subject and number (e.g., "CHM 1045")
                    course_code = parts[0][:3] + " " + parts[0][3:]
                    original_line = line
                    
                    # Look ahead for continuation lines
                    full_description = []
                    current_line = line
                    while True:
                        if current_line == line:
                            current_line = current_line.replace(parts[0], '', 1)
                        full_description.append(current_line.strip())
                        
                        if i + 1 < len(lines) and lines[i + 1].strip():
                            next_line = lines[i + 1].strip()
                            if not re.match(r'^[A-Z]{3}\d{4}', next_line) and not re.match(r'^(Term|Transfer|Combined|Cum)', next_line):
                                i += 1
                                current_line = next_line
                                continue
                        break
                    
                    # Join all description lines
                    full_text = ' '.join(full_description)
                    
                    # Extract grade
                    grade_match = re.search(r'([A-Z][+-]?)GRD', full_text)
                    if grade_match:
                        grade = grade_match.group(1)
                        full_text = full_text.replace(grade_match.group(0), '')
                    else:
                        grade = "N/A"
                    
                    # Extract credits
                    credits_match = re.search(r'(\d+\.\d+)\s+(?:\d+\.\d+)?\s*$', full_text)
                    if credits_match:
                        credits = float(credits_match.group(1))
                        full_text = re.sub(r'\s+\d+\.\d+(?:\s+\d+\.\d+)*\s*$', '', full_text)
                    else:
                        credits = 0.0
                    
                    # Clean up the course name
                    course_name = full_text.strip()
                    course_name = re.sub(r'\s+\d+(?:\.\d+)?\s*', ' ', course_name)
                    course_name = re.sub(r'\s+', ' ', course_name)
                    course_name = course_name.strip()
                    course_name = re.sub(r'[,.:]+$', '', course_name)
                    
                    if "TRN TEST" in course_name:
                        i += 1
                        continue
                    
                    if course_name.endswith(grade):
                        course_name = course_name[:-len(grade)].strip()
                    
                    current_semester["courses"].append({
                        "course_code": course_code,
                        "course_name": course_name,
                        "grade": grade,
                        "credits": credits
                    })
                    i += 1
                    continue
                
                # Check for Term GPA
                term_gpa_match = re.match(r'^Term GPA\s+(\d+\.\d+)', line)
                if term_gpa_match and current_semester:
                    current_semester["gpa"] = float(term_gpa_match.group(1))
                    i += 1
                    continue
                
                # Check for Combined Cum GPA
                cum_gpa_match = re.match(r'^Combined Cum GPA\s+(\d+\.\d+)', line)
                if cum_gpa_match:
                    result["cumulative_gpa"] = float(cum_gpa_match.group(1))
                    i += 1
                    continue
                
                i += 1
        
        # Add the last semester if exists
        if current_semester:
            result["semesters"].append(current_semester)
        
        return result

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Process academic transcripts into structured JSON")
    parser.add_argument("file_path", help="Path to the PDF transcript file")
    parser.add_argument("--output", help="Output JSON file path", default="output.json")
    parser.add_argument("--chunk-size", type=int, help="Maximum number of characters per chunk", default=1000)
    
    args = parser.parse_args()
    
    processor = DocumentProcessor(chunk_size=args.chunk_size)
    result = processor.process_document(args.file_path)
    
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Transcript processed and saved to {args.output}")

if __name__ == "__main__":
    main()
