import json
from itertools import combinations
from datetime import datetime, time

class ScheduleGenerator:
    def __init__(self, eligible_courses):
        self.eligible_courses = eligible_courses
        
    def parse_time(self, time_str):
        """Parse time string to datetime object."""
        if time_str == "12:00:00 AM" or not time_str:
            return None
        return datetime.strptime(time_str, "%I:%M:%S %p").time()
    
    def parse_days(self, days_str):
        """Parse meeting days string into a list of days."""
        if not days_str:
            return []
        day_map = {"Mo": "Monday", "Tu": "Tuesday", "We": "Wednesday", 
                   "Th": "Thursday", "Fr": "Friday", "Sa": "Saturday", "Su": "Sunday"}
        days = []
        i = 0
        while i < len(days_str):
            if i + 1 < len(days_str):
                day_code = days_str[i:i+2]
                if day_code in day_map:
                    days.append(day_map[day_code])
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        return days
    
    def has_time_conflict(self, course1, course2):
        """Check if two courses have a time conflict."""
        days1 = self.parse_days(course1["meeting_days"])
        days2 = self.parse_days(course2["meeting_days"])
        
        # No conflict if they don't meet on the same days
        if not set(days1).intersection(set(days2)):
            return False
        
        # No conflict if either is online/asynchronous
        start1 = self.parse_time(course1["meeting_start"])
        end1 = self.parse_time(course1["meeting_end"])
        start2 = self.parse_time(course2["meeting_start"])
        end2 = self.parse_time(course2["meeting_end"])
        
        if not all([start1, end1, start2, end2]):
            return False
        
        # Check for time overlap
        return not (end1 <= start2 or end2 <= start1)
    
    def has_duplicate_courses(self, courses):
        """Check if schedule contains duplicate courses (same course code)."""
        course_codes = [course["course_code"] for course in courses]
        return len(course_codes) != len(set(course_codes))
    
    def meets_constraints(self, schedule, constraints):
        """Check if a schedule meets all constraints."""
        # Check total credits
        total_credits = sum(course.get("credit_hours", 3) for course in schedule)
        if total_credits > constraints["max_credits"]:
            return False
        
        # Check each course
        for course in schedule:
            # Skip checks for online courses
            if course.get("location", "").lower() == "online":
                continue
            
            # Parse meeting times
            start_time = self.parse_time(course.get("meeting_start", ""))
            end_time = self.parse_time(course.get("meeting_end", ""))
            
            # Skip time checks if no meeting times
            if not start_time or not end_time:
                continue
            
            # Check earliest time constraint
            if constraints["earliest_time"] and start_time < constraints["earliest_time"]:
                return False
            
            # Check latest time constraint
            if constraints["latest_time"] and end_time > constraints["latest_time"]:
                return False
            
            # Check excluded days
            course_days = self.parse_days(course.get("meeting_days", ""))
            if any(day in constraints["excluded_days"] for day in course_days):
                return False
            
            # Check online only constraint
            if constraints["online_only"] and course.get("location", "").lower() != "online":
                return False
        
        return True
    
    def generate_schedules(self, constraints):
        """Generate possible schedules based on constraints."""
        all_courses = []
        
        # Deduplicate courses (same course, different instructors)
        unique_courses = {}
        for course in self.eligible_courses:
            key = (course["course_code"], course["section"], course["session"], 
                   course["meeting_days"], course["meeting_start"], course["meeting_end"])
            if key not in unique_courses:
                unique_courses[key] = course
        
        all_courses = list(unique_courses.values())
        
        valid_schedules = []
        
        # Try combinations of different sizes up to max credits
        max_courses = constraints.get("max_credits", 15) // 3
        
        for i in range(1, min(max_courses + 1, len(all_courses) + 1)):
            for combo in combinations(all_courses, i):
                # Check for duplicate courses
                if self.has_duplicate_courses(combo):
                    continue
                
                # Check for time conflicts within the combination
                has_conflict = False
                for idx1 in range(len(combo)):
                    for idx2 in range(idx1 + 1, len(combo)):
                        if self.has_time_conflict(combo[idx1], combo[idx2]):
                            has_conflict = True
                            break
                    if has_conflict:
                        break
                
                if not has_conflict and self.meets_constraints(combo, constraints):
                    schedule_info = {
                        "total_credits": len(combo) * 3,
                        "courses": []
                    }
                    
                    for course in combo:
                        course_info = {
                            "course_code": course["course_code"],
                            "title": course["title"],
                            "section": course["section"],
                            "session": course["session"],
                            "meeting_days": course["meeting_days"],
                            "meeting_time": f"{course['meeting_start']} - {course['meeting_end']}",
                            "location": course["location"],
                            "instructor": course["instructor"],
                            "required_for": course["required_for"]
                        }
                        schedule_info["courses"].append(course_info)
                    
                    valid_schedules.append(schedule_info)
        
        return valid_schedules

def generate_schedules_with_constraints(max_credits=15, earliest_time=None, latest_time=None, 
                                     excluded_days=None, online_only=False, output_file='schedules.json',
                                     interest_courses_file=None, eligible_courses_file='../eligible_courses.json'):
    """Generate schedules with user-specified constraints and optional interest courses."""
    # Load eligible courses
    try:
        with open(eligible_courses_file, 'r') as file:
            data = json.load(file)
        
        eligible_courses = data.get("eligible_courses", [])
        
        # Load and add interest courses if provided
        if interest_courses_file:
            with open(interest_courses_file, 'r') as file:
                interest_courses = json.load(file)
                
                # Add interest courses to eligible courses
                for course in interest_courses:
                    # Add identifier that this is an interest course
                    course["required_for"] = ["Personal Interest"]
                    eligible_courses.append(course)
        
        generator = ScheduleGenerator(eligible_courses)
        
        # Default constraints
        constraints = {
            "max_credits": max_credits,
            "earliest_time": earliest_time,
            "latest_time": latest_time,
            "excluded_days": excluded_days if excluded_days is not None else [],
            "online_only": online_only
        }
        
        # Generate schedules
        schedules = generator.generate_schedules(constraints)
        
        # Sort schedules by number of credits (descending)
        schedules.sort(key=lambda x: x["total_credits"], reverse=True)
        
        # Categorize courses in schedules
        for schedule in schedules:
            schedule["course_types"] = {
                "required": 0,
                "interest": 0
            }
            
            for course in schedule["courses"]:
                if "required_for" in course and "Personal Interest" in course["required_for"]:
                    schedule["course_types"]["interest"] += 1
                else:
                    schedule["course_types"]["required"] += 1
        
        # Save to file
        with open(output_file, 'w') as f:
            json.dump({
                "schedule_count": len(schedules),
                "schedules": schedules,
                "constraints": constraints
            }, f, indent=2)
        
        return schedules
        
    except Exception as e:
        print(f"Error generating schedules: {str(e)}")
        return []

def main():
    """Main function with example usage."""
    # Default schedule generation (15 credits, all days, no time restrictions)
    print("Generating default schedule (15 credits, no restrictions)...")
    default_schedules = generate_schedules_with_constraints(output_file='default_schedules.json')
    
    # Example with constraints
    print("\nGenerating constrained schedule...")
    constrained_schedules = generate_schedules_with_constraints(
        max_credits=12,
        earliest_time=time(9, 0),
        latest_time=time(17, 0),
        excluded_days=["Friday"],
        online_only=False,
        output_file='constrained_schedules.json'
    )

if __name__ == "__main__":
    main()