import json
import argparse
from datetime import time
from schedulegen import ScheduleGenerator, generate_schedules_with_constraints

def parse_time_arg(time_str):
    """Parse time string argument (e.g., '9:00' or '14:30')."""
    if not time_str:
        return None
    try:
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    except:
        raise argparse.ArgumentTypeError(f"Invalid time format: {time_str}. Use HH:MM format.")

def parse_days_arg(days_str):
    """Parse comma-separated days string."""
    if not days_str:
        return []
    days_map = {
        'monday': 'Monday', 'mon': 'Monday', 'm': 'Monday',
        'tuesday': 'Tuesday', 'tue': 'Tuesday', 't': 'Tuesday',
        'wednesday': 'Wednesday', 'wed': 'Wednesday', 'w': 'Wednesday',
        'thursday': 'Thursday', 'thu': 'Thursday', 'r': 'Thursday',
        'friday': 'Friday', 'fri': 'Friday', 'f': 'Friday',
        'saturday': 'Saturday', 'sat': 'Saturday', 's': 'Saturday',
        'sunday': 'Sunday', 'sun': 'Sunday', 'u': 'Sunday'
    }
    
    days = []
    for day in days_str.lower().split(','):
        day = day.strip()
        if day in days_map:
            days.append(days_map[day])
        else:
            print(f"Warning: Unknown day '{day}', skipping.")
    return days

def main():
    parser = argparse.ArgumentParser(description='Generate course schedules based on constraints')
    
    parser.add_argument('--max-credits', type=int, default=15,
                        help='Maximum number of credits (default: 15)')
    parser.add_argument('--earliest', type=parse_time_arg,
                        help='Earliest class time (format: HH:MM, e.g., 9:00)')
    parser.add_argument('--latest', type=parse_time_arg,
                        help='Latest class end time (format: HH:MM, e.g., 17:00)')
    parser.add_argument('--exclude-days', type=parse_days_arg,
                        help='Days to exclude (comma-separated, e.g., Monday,Friday)')
    parser.add_argument('--online-only', action='store_true',
                        help='Include only online courses')
    parser.add_argument('--output', default='generated_schedules.json',
                        help='Output JSON file name (default: generated_schedules.json)')
    parser.add_argument('--interest-courses', type=str,
                        help='JSON file containing additional interest courses')
    parser.add_argument('--eligible-courses', type=str, default='../eligible_courses.json',
                        help='JSON file containing eligible courses (default: ../eligible_courses.json)')
    
    args = parser.parse_args()
    
    # Generate schedules with specified constraints
    schedules = generate_schedules_with_constraints(
        max_credits=args.max_credits,
        earliest_time=args.earliest,
        latest_time=args.latest,
        excluded_days=args.exclude_days,
        online_only=args.online_only,
        output_file=args.output,
        interest_courses_file=args.interest_courses,
        eligible_courses_file=args.eligible_courses
    )
    
    # Display summary
    print(f"\nGenerated {len(schedules)} valid schedules")
    if schedules:
        print(f"Most credits in a schedule: {schedules[0]['total_credits']}")
        print(f"First schedule includes:")
        
        # Separate required and interest courses
        required_courses = []
        interest_courses = []
        
        for course in schedules[0]['courses']:
            if "Personal Interest" in course['required_for']:
                interest_courses.append(course)
            else:
                required_courses.append(course)
        
        if required_courses:
            print("\nRequired courses:")
            for i, course in enumerate(required_courses, 1):
                print(f"  {i}. {course['course_code']}: {course['title']}")
                print(f"     {course['meeting_days']} {course['meeting_time']}")
                print(f"     {course['location']}")
        
        if interest_courses:
            print("\nInterest courses:")
            for i, course in enumerate(interest_courses, 1):
                print(f"  {i}. {course['course_code']}: {course['title']}")
                print(f"     {course['meeting_days']} {course['meeting_time']}")
                print(f"     {course['location']}")
        
        print(f"\nCourse breakdown: {schedules[0]['course_types']['required']} required, {schedules[0]['course_types']['interest']} interest")

if __name__ == "__main__":
    main()