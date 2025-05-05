import json
import subprocess
import requests
from typing import Dict, List, Any, Optional
from qdrant_client import QdrantClient

class CourseSchedulerTool:
    def __init__(self, qdrant_host: str = "localhost", qdrant_port: int = 6333):
        """Initialize the course search and scheduling tool."""
        self.qdrant_client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.collection_name = "courses"
        self.embedding_model_url = "http://localhost:11434/api/embeddings"
        
    def get_embeddings(self, text: str) -> List[float]:
        """Get embeddings using nomic-embed-text via Ollama."""
        payload = {
            "model": "nomic-embed-text",
            "prompt": text
        }
        
        try:
            response = requests.post(self.embedding_model_url, json=payload)
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            print(f"Error getting embeddings: {e}")
            return []
    
    def search_courses_by_interest(self, interest_query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for courses based on student's interests."""
        query_embedding = self.get_embeddings(interest_query)
        
        if not query_embedding:
            return []
        
        search_result = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit
        )
        
        # Extract and structure the results
        courses = []
        for hit in search_result:
            subject = hit.payload["subject"]
            text = hit.payload["text"]
            
            # Parse the course information from the text
            course_blocks = text.split("---\n")
            for block in course_blocks:
                if not block.strip():
                    continue
                    
                course_info = {}
                lines = block.strip().split("\n")
                for line in lines:
                    if ": " in line:
                        key, value = line.split(": ", 1)
                        course_info[key.lower().replace(" ", "_")] = value
                
                if "course_code" in course_info:
                    courses.append({
                        "course_code": course_info.get("course_code", ""),
                        "title": course_info.get("title", ""),
                        "subject": subject,
                        "score": hit.score
                    })
        
        return courses[:limit]
    
    def generate_interest_courses_file(self, courses: List[Dict[str, Any]], 
                                     eligible_courses_json: str = "../eligible_courses.json",
                                     output_file: str = "interest_courses.json") -> None:
        """Create interest courses JSON file compatible with the scheduler."""
        
        # Load eligible courses to match format
        with open(eligible_courses_json, 'r') as f:
            eligible_data = json.load(f)
            
        eligible_courses = eligible_data.get("eligible_courses", [])
        
        # Match interest courses with available sections
        interest_course_data = []
        for interest_course in courses:
            # Find matching courses in eligible list
            matches = [
                ec for ec in eligible_courses 
                if ec["course_code"] == interest_course["course_code"]
            ]
            
            # Add all sections of this course
            for match in matches:
                course_json = {
                    "course_code": match["course_code"],
                    "title": match["title"],
                    "section": match["section"],
                    "session": match["session"],
                    "meeting_days": match["meeting_days"],
                    "meeting_start": match["meeting_start"],
                    "meeting_end": match["meeting_end"],
                    "facility": match["facility"],
                    "instructor": match["instructor"],
                    "location": match["location"],
                    "credit_hours": 3,  # Assuming 3 credit hours
                    "prerequisites": None
                }
                interest_course_data.append(course_json)
        
        # Save to file
        with open(output_file, 'w') as f:
            json.dump(interest_course_data, f, indent=2)
        
        return output_file
    
    def run_scheduler_with_interests(self, interest_query: str, 
                                   max_credits: int = 15,
                                   earliest_time: Optional[str] = None,
                                   latest_time: Optional[str] = None,
                                   exclude_days: Optional[List[str]] = None,
                                   online_only: bool = False) -> Dict[str, Any]:
        """Search for interest courses and generate schedules."""
        
        # 1. Search for courses based on interests
        interest_courses = self.search_courses_by_interest(interest_query)
        
        # 2. Generate interest courses JSON file
        interest_file = self.generate_interest_courses_file(interest_courses)
        
        # 3. Build scheduler command
        scheduler_cmd = [
            "python", "./schedulegencli.py",
            "--max-credits", str(max_credits),
            "--interest-courses", interest_file,
            "--output", "../interest_based_schedule.json",
            "--eligible-courses", "../eligible_courses.json"
        ]
        
        if earliest_time:
            scheduler_cmd.extend(["--earliest", earliest_time])
        if latest_time:
            scheduler_cmd.extend(["--latest", latest_time])
        if exclude_days:
            scheduler_cmd.extend(["--exclude-days", ",".join(exclude_days)])
        if online_only:
            scheduler_cmd.append("--online-only")
        
        # 4. Run the scheduler
        try:
            result = subprocess.run(scheduler_cmd, capture_output=True, text=True)
            
            # 5. Load the generated schedules
            with open("../interest_based_schedule.json", 'r') as f:
                schedules = json.load(f)
            
            return {
                "status": "success",
                "interest_courses_found": interest_courses,
                "schedule_count": schedules.get("schedule_count", 0),
                "best_schedule": schedules.get("schedules", [{}])[0] if schedules.get("schedules") else None,
                "scheduler_output": result.stdout
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

# Tool definition for Ollama to use
TOOL_DEFINITION = {
    "name": "course_scheduler",
    "description": "Search for courses based on student interests and generate optimal schedules",
    "parameters": {
        "type": "object",
        "properties": {
            "interest_query": {
                "type": "string",
                "description": "Natural language description of student's course interests"
            },
            "max_credits": {
                "type": "integer",
                "description": "Maximum credits per semester (default 15)"
            },
            "earliest_time": {
                "type": "string",
                "description": "Earliest class time in HH:MM format"
            },
            "latest_time": {
                "type": "string",
                "description": "Latest class time in HH:MM format"
            },
            "exclude_days": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Days to exclude (e.g. Monday, Friday)"
            },
            "online_only": {
                "type": "boolean",
                "description": "Whether to include only online courses"
            }
        },
        "required": ["interest_query"]
    }
}

# Example usage function for testing
def test_tool():
    tool = CourseSchedulerTool()
    
    # Test search
    result = tool.run_scheduler_with_interests(
        interest_query="I'm interested in data science, machine learning, and artificial intelligence",
        max_credits=15,
        exclude_days=["Friday"]
    )
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test_tool()