import json
import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
import requests
from tqdm import tqdm

class CourseVectorLoader:
    def __init__(self, qdrant_host: str = "localhost", qdrant_port: int = 6333, collection_name: str = "courses"):
        """Initialize the Qdrant client and collection."""
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.collection_name = collection_name
        self.embedding_model_url = "http://localhost:11434/api/embeddings"  # Ollama embeddings endpoint
    
    def create_collection(self, vector_size: int = 768):  # Default size for nomic-embed-text
        """Create a Qdrant collection for course data."""
        try:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            print(f"Created collection: {self.collection_name}")
        except Exception as e:
            print(f"Error creating collection: {e}")
    
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
    
    def create_course_chunk(self, subject: str, courses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a rich text representation of courses in a subject."""
        chunk_text = f"Subject: {subject}\n\n"
        
        for course in courses:
            chunk_text += f"Course Code: {course.get('course_code', 'N/A')}\n"
            chunk_text += f"Title: {course.get('title', 'N/A')}\n"
            
            if 'prerequisites' in course and course['prerequisites']:
                chunk_text += f"Prerequisites: {course['prerequisites']}\n"
            
            if 'credit_hours' in course:
                chunk_text += f"Credit Hours: {course['credit_hours']}\n"
            
            if 'description' in course:
                chunk_text += f"Description: {course['description']}\n"
            
            chunk_text += "---\n"
        
        return {
            "text": chunk_text,
            "metadata": {
                "subject": subject,
                "course_count": len(courses),
                "course_codes": [c.get('course_code', '') for c in courses]
            }
        }
    
    def load_and_index_courses(self, courselist_path: str):
        """Load courses from JSON and index them in Qdrant."""
        # Load course data
        with open(courselist_path, 'r') as f:
            course_data = json.load(f)
        
        # Group courses by subject
        courses_by_subject = {}
        for course in course_data:
            subject = course.get('course_code', '').split()[0] if course.get('course_code') else 'UNKNOWN'
            if subject not in courses_by_subject:
                courses_by_subject[subject] = []
            courses_by_subject[subject].append(course)
        
        # Create chunks and index them
        points = []
        for idx, (subject, courses) in enumerate(tqdm(courses_by_subject.items(), desc="Processing subjects")):
            chunk = self.create_course_chunk(subject, courses)
            embedding = self.get_embeddings(chunk["text"])
            
            if embedding:
                point = models.PointStruct(
                    id=idx,
                    vector=embedding,
                    payload={
                        "subject": subject,
                        "text": chunk["text"],
                        "metadata": chunk["metadata"]
                    }
                )
                points.append(point)
        
        # Index in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
            print(f"Indexed batch {i//batch_size + 1}")
    
    def search_courses(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search for courses based on natural language query."""
        query_embedding = self.get_embeddings(query)
        
        if not query_embedding:
            return []
        
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit
        )
        
        results = []
        for hit in search_result:
            results.append({
                "subject": hit.payload["subject"],
                "text": hit.payload["text"],
                "score": hit.score,
                "metadata": hit.payload["metadata"]
            })
        
        return results

def main():
    # Example usage
    loader = CourseVectorLoader()
    
    # Create collection
    loader.create_collection()
    
    # Load and index courses from JSON file
    loader.load_and_index_courses("../courselist.json")
    
    # Test search
    test_query = "I'm interested in programming and computer science courses"
    results = loader.search_courses(test_query)
    
    print("\nSearch Results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. Subject: {result['subject']} (Score: {result['score']:.3f})")
        print(f"Courses: {', '.join(result['metadata']['course_codes'])}")

if __name__ == "__main__":
    main()