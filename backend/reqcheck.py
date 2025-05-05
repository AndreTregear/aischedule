import json
import sys
import os
from typing import Dict, Any, Set

def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load a JSON file with UTF-8 BOM handling."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

def extract_completed_courses(transcript: Dict[str, Any]) -> Set[str]:
    """Extract completed courses from the transcript data"""
    completed_courses = set()
    for semester in transcript.get('semesters', []):
        for course in semester.get('courses', []):
            # Only count courses that weren't withdrawn (grade != 'W')
            if course.get('grade') != 'W':
                completed_courses.add(course.get('course_code'))
    return completed_courses

def check_requirements(transcript: Dict[str, Any], program: Dict[str, Any], major_name: str = None) -> Dict[str, Any]:
    """Check which requirements have been completed and which are still needed"""
    completed_courses = extract_completed_courses(transcript)
    
    results = {
        "major_name": major_name or program.get('major', 'Major'),
        "degree": program.get('degree'),
        "lower_level_prerequisites": {"completed": [], "remaining": []},
        "general_business_core": {"completed": [], "remaining": []},
        "general_business_breadth": {"completed": [], "remaining": []},
        "major_requirements": {"completed": [], "remaining": []},
        "electives_taken": [],
        "electives_needed": 0,
        "electives_available": []
    }
    
    # Check lower level prerequisites
    for course in program.get('lower_level_prerequisites', []):
        course_code = course.get('course_code')
        if course_code in completed_courses:
            results["lower_level_prerequisites"]["completed"].append(course)
        else:
            results["lower_level_prerequisites"]["remaining"].append(course)
    
    # Check general business core requirements
    for course in program.get('general_business_core_requirements', []):
        course_code = course.get('course_code')
        if course_code in completed_courses:
            results["general_business_core"]["completed"].append(course)
        else:
            results["general_business_core"]["remaining"].append(course)
    
    # Check general business breadth requirements
    breadth_reqs = program.get('general_business_breadth_requirements', {})
    if isinstance(breadth_reqs, dict):
        # Required breadth courses
        for course in breadth_reqs.get('required', []):
            course_code = course.get('course_code')
            if course_code in completed_courses:
                results["general_business_breadth"]["completed"].append(course)
            else:
                results["general_business_breadth"]["remaining"].append(course)
        
        # Breadth electives (need 2 from options)
        breadth_electives_taken = []
        for course in breadth_reqs.get('electives_choose_two', []):
            course_code = course.get('course_code')
            if course_code in completed_courses:
                breadth_electives_taken.append(course)
        
        results["general_business_breadth"]["completed"].extend(breadth_electives_taken)
        if len(breadth_electives_taken) < 2:
            results["general_business_breadth"]["remaining"].append({
                "type": "elective_requirement",
                "required": 2,
                "completed": len(breadth_electives_taken),
                "remaining": 2 - len(breadth_electives_taken),
                "options": breadth_reqs.get('electives_choose_two', [])
            })
    elif isinstance(breadth_reqs, list):
        # If breadth_reqs is a list, treat all courses as required
        for course in breadth_reqs:
            course_code = course.get('course_code')
            if course_code in completed_courses:
                results["general_business_breadth"]["completed"].append(course)
            else:
                results["general_business_breadth"]["remaining"].append(course)
    
    # Check major requirements
    major_area = program.get('major_area_requirements', {})
    
    # Required major courses
    for course in major_area.get('required_courses', []):
        course_code = course.get('course_code')
        if course_code in completed_courses:
            results["major_requirements"]["completed"].append(course)
        else:
            results["major_requirements"]["remaining"].append(course)
    
    # Major electives
    major_electives_taken = []
    for course in major_area.get('electives', []):
        course_code = course.get('course_code')
        if course_code in completed_courses:
            major_electives_taken.append(course)
    
    results["electives_taken"] = major_electives_taken
    results["electives_needed"] = max(0, major_area.get('requiredElectives', 0) - len(major_electives_taken))
    results["electives_available"] = [
        elective for elective in major_area.get('electives', [])
        if elective.get('course_code') not in completed_courses
    ]
    
    return results

def combine_major_requirements(requirements1: Dict[str, Any], requirements2: Dict[str, Any] = None) -> Dict[str, Any]:
    """Combine requirements from two majors, handling shared general education requirements"""
    if not requirements2:
        return requirements1
    
    combined = {
        "majors": [requirements1["major_name"], requirements2["major_name"]],
        "degrees": [requirements1["degree"], requirements2["degree"]],
        "shared_requirements": {
            "lower_level_prerequisites": {"completed": [], "remaining": []},
            "general_business_core": {"completed": [], "remaining": []},
            "general_business_breadth": {"completed": [], "remaining": []}
        },
        "major_specific_requirements": {
            requirements1["major_name"]: {
                "major_requirements": requirements1["major_requirements"],
                "electives_taken": requirements1["electives_taken"],
                "electives_needed": requirements1["electives_needed"],
                "electives_available": requirements1["electives_available"]
            },
            requirements2["major_name"]: {
                "major_requirements": requirements2["major_requirements"],
                "electives_taken": requirements2["electives_taken"],
                "electives_needed": requirements2["electives_needed"],
                "electives_available": requirements2["electives_available"]
            }
        }
    }
    
    # Since both majors likely share general requirements, merge them
    for category in ["lower_level_prerequisites", "general_business_core", "general_business_breadth"]:
        # Combine completed courses (avoiding duplicates)
        completed_codes = set()
        for req in requirements1[category]["completed"] + requirements2[category]["completed"]:
            course_code = req.get("course_code") if isinstance(req, dict) else None
            if course_code and course_code not in completed_codes:
                completed_codes.add(course_code)
                combined["shared_requirements"][category]["completed"].append(req)
        
        # For remaining courses, only include if not completed in either major
        for req in requirements1[category]["remaining"] + requirements2[category]["remaining"]:
            if isinstance(req, dict):
                course_code = req.get("course_code")
                if course_code and course_code not in completed_codes:
                    completed_codes.add(course_code)
                    combined["shared_requirements"][category]["remaining"].append(req)
            else:
                # Handle elective requirements specially
                combined["shared_requirements"][category]["remaining"].append(req)
    
    return combined

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Course Schedule Optimizer for Single or Double Major')
    parser.add_argument('transcript', help='Path to transcript JSON file')
    parser.add_argument('major1', help='Path to first major requirements JSON file')
    parser.add_argument('--major2', help='Path to second major requirements JSON file (optional)', default=None)
    args = parser.parse_args()
    
    # Load data from files
    try:
        transcript = load_json_file(args.transcript)
        program1 = load_json_file(args.major1)
        program2 = load_json_file(args.major2) if args.major2 else None
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Check requirements for both majors
    requirements_status1 = check_requirements(transcript, program1, major_name=program1.get("major", "Major 1"))
    requirements_status2 = check_requirements(transcript, program2, major_name=program2.get("major", "Major 2")) if program2 else None
    
    # Combine requirements
    combined_requirements = combine_major_requirements(requirements_status1, requirements_status2)
    
    # Prepare final output
    output = {
        "student_id": transcript.get("student_info", {}).get("id"),
        "program": {
            "majors": combined_requirements.get("majors", [program1.get("major")]),
            "degrees": combined_requirements.get("degrees", [program1.get("degree")]),
            "academic_year": program1.get("academic_year")
        },
        "requirements_status": combined_requirements,
        "summary": {
            "is_double_major": program2 is not None
        }
    }
    
    # Output as JSON
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()