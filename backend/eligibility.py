import json
import argparse

def load_json_file(filename):
    """Load and parse a JSON file."""
    with open(filename, 'r') as file:
        return json.load(file)

def get_completed_courses(student_data):
    """Extract all completed courses from student data."""
    completed_courses = []
    
    # Get completed courses from shared requirements
    shared_reqs = student_data["requirements_status"]["shared_requirements"]
    
    # Add completed lower level prerequisites
    for course in shared_reqs["lower_level_prerequisites"]["completed"]:
        completed_courses.append(course["course_code"])
    
    # Add completed general business core
    for course in shared_reqs["general_business_core"]["completed"]:
        completed_courses.append(course["course_code"])
    
    # Add completed general business breadth
    for course in shared_reqs["general_business_breadth"]["completed"]:
        completed_courses.append(course["course_code"])
    
    # Add completed major-specific requirements
    major_specific = student_data["requirements_status"]["major_specific_requirements"]
    
    for major, details in major_specific.items():
        # Add completed major requirements
        for course in details["major_requirements"]["completed"]:
            completed_courses.append(course["course_code"])
        
        # Add completed electives
        for course in details["electives_taken"]:
            completed_courses.append(course["course_code"])
    
    return completed_courses

def get_remaining_courses(student_data):
    """Extract all remaining courses from student data."""
    remaining_courses = []
    
    # Get remaining courses from shared requirements
    shared_reqs = student_data["requirements_status"]["shared_requirements"]
    
    # Add remaining lower level prerequisites
    for course in shared_reqs["lower_level_prerequisites"]["remaining"]:
        remaining_courses.append({
            "course_code": course["course_code"],
            "title": course["title"],
            "prerequisites": course["prerequisites"]
        })
    
    # Add remaining general business core
    for course in shared_reqs["general_business_core"]["remaining"]:
        remaining_courses.append({
            "course_code": course["course_code"],
            "title": course["title"],
            "prerequisites": course["prerequisites"]
        })
    
    # Add remaining general business breadth
    for course in shared_reqs["general_business_breadth"]["remaining"]:
        remaining_courses.append({
            "course_code": course["course_code"],
            "title": course["title"],
            "prerequisites": course["prerequisites"]
        })
    
    # Add remaining major-specific requirements
    major_specific = student_data["requirements_status"]["major_specific_requirements"]
    
    for major, details in major_specific.items():
        # Add remaining major requirements
        for course in details["major_requirements"]["remaining"]:
            remaining_courses.append({
                "course_code": course["course_code"],
                "title": course["title"],
                "prerequisites": course["prerequisites"]
            })
    
    return remaining_courses

def check_prerequisites_met(course_prerequisites, completed_courses):
    """Check if all prerequisites for a course are met."""
    if not course_prerequisites:
        return True
    
    # Handle when prerequisites is a list
    if isinstance(course_prerequisites, list):
        for prereq in course_prerequisites:
            if prereq not in completed_courses:
                return False
        return True
    
    # Handle when prerequisites is a string (single course)
    if isinstance(course_prerequisites, str):
        return course_prerequisites in completed_courses
    
    return True

def find_eligible_courses(student_data, course_offerings):
    """Find courses student is eligible to take based on prerequisites."""
    completed_courses = get_completed_courses(student_data)
    remaining_courses = get_remaining_courses(student_data)
    
    # Create a dictionary for quick lookup
    remaining_courses_dict = {course["course_code"]: course for course in remaining_courses}
    
    eligible_courses = []
    
    for offering in course_offerings:
        course_code = offering["course_code"]
        
        # Check if this course is in the remaining list
        if course_code in remaining_courses_dict:
            course = remaining_courses_dict[course_code]
            
            # Check if prerequisites are met
            if check_prerequisites_met(course["prerequisites"], completed_courses):
                eligible_courses.append({
                    "course_code": course_code,
                    "title": offering["title"],
                    "section": offering["section"],
                    "session": offering["session"],
                    "meeting_days": offering["meeting_days"],
                    "meeting_start": offering["meeting_start"],
                    "meeting_end": offering["meeting_end"],
                    "facility": offering["facility"],
                    "instructor": offering["instructor"],
                    "location": offering["location"],
                    "prerequisites_met": True,
                    "required_for": []
                })
                
                # Determine what requirement this course fulfills
                if course_code in ["CGS 2100", "GEB 1030"]:
                    eligible_courses[-1]["required_for"].append("Lower Level Prerequisites")
                elif course_code in ["ECO 2013", "ECO 2023", "MAC 2233", "STA 2023", "CGS 2518", "ACG 2021", "ACG 2071", "RMI 2302"]:
                    eligible_courses[-1]["required_for"].append("Lower Level Prerequisites")
                elif course_code in ["BUL 3310", "FIN 3403", "GEB 3213", "ISM 3541", "MAN 3240", "MAR 3023"]:
                    eligible_courses[-1]["required_for"].append("General Business Core")
                elif course_code in ["MAN 4720", "FIN 3244", "QMB 3200"]:
                    eligible_courses[-1]["required_for"].append("General Business Breadth")
                elif course_code in ["ISM 4113", "ISM 4212", "ISM 4220"]:
                    eligible_courses[-1]["required_for"].append("Management Information Systems Major")
                elif course_code in ["FIN 4424", "FIN 4504", "ACG 3171", "ACG 3331"]:
                    eligible_courses[-1]["required_for"].append("Finance Major")
    
    return eligible_courses

def save_to_json(data, filename):
    """Save data to a JSON file."""
    with open(filename, 'w') as file:
        json.dump(data, file, indent=2)

def main():
    """Main function to find eligible courses and save to JSON."""
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Check course eligibility based on requirements and course offerings')
    parser.add_argument('courselist', help='Path to course offerings JSON file')
    parser.add_argument('requirements', help='Path to requirements JSON file')
    parser.add_argument('--output', default='eligible_courses.json', help='Output file path (default: eligible_courses.json)')
    
    args = parser.parse_args()
    
    # Load the student data and course offerings
    student_data = load_json_file(args.requirements)
    course_offerings = load_json_file(args.courselist)
    
    # Find eligible courses
    eligible_courses = find_eligible_courses(student_data, course_offerings)
    
    # Create output data structure
    output = {
        "student_id": student_data["student_id"],
        "analysis_date": "2025-05-05",
        "total_eligible_courses": len(eligible_courses),
        "eligible_courses": eligible_courses
    }
    
    # Save to JSON file
    save_to_json(output, args.output)
    
    # Print summary
    print(f"Total eligible courses found: {len(eligible_courses)}")
    print("\nCourses eligible to take this semester:")
    for course in eligible_courses:
        print(f"- {course['course_code']}: {course['title']}")
        print(f"  Session: {course['session']}")
        print(f"  Days: {course['meeting_days']}")
        print(f"  Time: {course['meeting_start']} - {course['meeting_end']}")
        print(f"  Location: {course['location']}")
        print(f"  Instructor: {course['instructor']}")
        print()

if __name__ == "__main__":
    main()