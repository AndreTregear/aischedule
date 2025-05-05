from flask import Flask, render_template, request, jsonify
import json
import os
import subprocess
from werkzeug.utils import secure_filename
from datetime import datetime, time
import PyPDF2
import re
from backend.ollamasearch import CourseSchedulerTool
from backend.schedulegen import ScheduleGenerator, generate_schedules_with_constraints

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global state for demo purposes (in production, use a database)
app_state = {
    'student_data': None,
    'eligible_courses': [],
    'current_schedule': None,
    'preferences': {},
    'chat_history': [],
    'required_courses': []
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    text = ""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
    return text

def parse_transcript(text):
    """Parse transcript text to extract completed courses"""
    # This is a simplified parser - you'd need to adapt based on actual transcript format
    completed_courses = []
    course_pattern = r'([A-Z]{3}\s+\d{4})\s+(.+?)\s+(\d+)\s+[A-F]'
    
    matches = re.finditer(course_pattern, text)
    for match in matches:
        course = {
            'course_code': match.group(1),
            'title': match.group(2).strip(),
            'credit_hours': int(match.group(3)),
            'prerequisites': None
        }
        completed_courses.append(course)
    
    return completed_courses

def parse_major_requirements(text):
    """Parse major requirements PDF to extract required courses"""
    # Simplified parser - adapt based on actual format
    required_courses = []
    # In practice, you'd need a more sophisticated parser
    # For now, let's use sample data
    
    if 'Management Information Systems' in text:
        required_courses.extend([
            {'course_code': 'CGS 2100', 'title': 'Microcomputer Applications', 'credit_hours': 3},
            {'course_code': 'ISM 4212', 'title': 'Data Management', 'credit_hours': 3},
            {'course_code': 'ISM 4220', 'title': 'Information Systems Management', 'credit_hours': 3}
        ])
    
    if 'Finance' in text:
        required_courses.extend([
            {'course_code': 'FIN 4504', 'title': 'Investments', 'credit_hours': 3},
            {'course_code': 'ACG 3171', 'title': 'Financial Statement Analysis', 'credit_hours': 3},
            {'course_code': 'ACG 3331', 'title': 'Cost Accounting', 'credit_hours': 3}
        ])
    
    return required_courses

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and process documents"""
    if 'transcript' not in request.files or 'major-requirements' not in request.files:
        return jsonify({'status': 'error', 'error': 'Missing files'})
    
    transcript_file = request.files['transcript']
    major_req_file = request.files['major-requirements']
    
    if transcript_file.filename == '' or major_req_file.filename == '':
        return jsonify({'status': 'error', 'error': 'No selected files'})
    
    try:
        # Save files
        transcript_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(transcript_file.filename))
        major_req_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(major_req_file.filename))
        
        transcript_file.save(transcript_path)
        major_req_file.save(major_req_path)
        
        # Extract text
        transcript_text = extract_text_from_pdf(transcript_path)
        major_req_text = extract_text_from_pdf(major_req_path)
        
        # Parse documents
        completed_courses = parse_transcript(transcript_text)
        required_courses = parse_major_requirements(major_req_text)
        
        # Update app state
        app_state['completed_courses'] = completed_courses
        app_state['required_courses'] = required_courses
        
        # Calculate remaining courses
        completed_codes = {course['course_code'] for course in completed_courses}
        remaining_courses = [
            course for course in required_courses 
            if course['course_code'] not in completed_codes
        ]
        
        # Calculate graduation info
        total_credits_completed = sum(course['credit_hours'] for course in completed_courses)
        total_credits_required = sum(course['credit_hours'] for course in required_courses)
        credits_remaining = total_credits_required - total_credits_completed
        semesters_until_grad = max(1, credits_remaining // 15)  # Assuming 15 credits per semester
        
        graduation_info = {
            'semesters_until_graduation': semesters_until_grad,
            'completed_credits': total_credits_completed,
            'remaining_credits': credits_remaining
        }
        
        # Clean up files
        os.remove(transcript_path)
        os.remove(major_req_path)
        
        return jsonify({
            'status': 'success',
            'required_courses': required_courses,
            'graduation_info': graduation_info
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/api/generate-schedule', methods=['POST'])
def generate_schedule():
    """Generate initial schedule based on requirements and preferences"""
    data = request.json
    required_courses = data.get('required_courses', [])
    preferences = data.get('preferences', {})
    
    try:
        # Convert preferences to constraints
        constraints = {
            'max_credits': preferences.get('max_credits', 15),
            'earliest_time': time(int(preferences.get('earliest_time', '8:00').split(':')[0]), 0) if preferences.get('earliest_time') else None,
            'latest_time': time(int(preferences.get('latest_time', '21:00').split(':')[0]), 0) if preferences.get('latest_time') else None,
            'excluded_days': preferences.get('exclude_days', []),
            'online_only': preferences.get('online_only', False)
        }
        
        # Load eligible courses (you'll need to implement this with actual course data)
        with open('eligible_courses.json', 'r') as f:
            eligible_courses = json.load(f)['eligible_courses']
        
        # Generate schedule
        generator = ScheduleGenerator(eligible_courses)
        schedules = generator.generate_schedules(constraints)
        
        if schedules:
            app_state['current_schedule'] = schedules[0]
            app_state['preferences'] = preferences
            
            return jsonify({
                'status': 'success',
                'schedule': schedules[0]
            })
        else:
            return jsonify({
                'status': 'error',
                'error': 'No valid schedules found with current constraints'
            })
            
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/api/alternative-schedules', methods=['POST'])
def get_alternative_schedules():
    """Get alternative schedule options"""
    data = request.json
    required_courses = data.get('required_courses', [])
    preferences = data.get('preferences', {})
    num_alternatives = data.get('num_alternatives', 3)
    
    try:
        # Add slight variations to preferences for alternatives
        alternatives = []
        
        # Alternative 1: Different time preference
        alt_prefs1 = preferences.copy()
        alt_prefs1['earliest_time'] = '9:00'
        
        # Alternative 2: Different days preference
        alt_prefs2 = preferences.copy()
        alt_prefs2['exclude_days'] = ['Monday'] if 'Friday' in preferences.get('exclude_days', []) else ['Friday']
        
        # Alternative 3: Different credit load
        alt_prefs3 = preferences.copy()
        alt_prefs3['max_credits'] = max(9, preferences.get('max_credits', 15) - 3)
        
        for i, alt_pref in enumerate([alt_prefs1, alt_prefs2, alt_prefs3][:num_alternatives]):
            constraints = {
                'max_credits': alt_pref.get('max_credits', 15),
                'earliest_time': time(int(alt_pref.get('earliest_time', '8:00').split(':')[0]), 0) if alt_pref.get('earliest_time') else None,
                'latest_time': time(int(alt_pref.get('latest_time', '21:00').split(':')[0]), 0) if alt_pref.get('latest_time') else None,
                'excluded_days': alt_pref.get('exclude_days', []),
                'online_only': alt_pref.get('online_only', False)
            }
            
            with open('eligible_courses.json', 'r') as f:
                eligible_courses = json.load(f)['eligible_courses']
            
            generator = ScheduleGenerator(eligible_courses)
            schedules = generator.generate_schedules(constraints)
            
            if schedules:
                alternatives.append({
                    'description': f'Alternative {i+1}: Different preferences',
                    'schedule': schedules[0]
                })
        
        return jsonify({
            'status': 'success',
            'alternatives': alternatives
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages and update schedule based on preferences"""
    data = request.json
    message = data.get('message', '')
    context = data.get('context', {})
    
    try:
        # Add to chat history
        app_state['chat_history'].append({'role': 'user', 'content': message})
        
        # Parse preferences from message
        preferences = {}
        
        # Parse common preferences
        if 'no evening' in message.lower() or 'after 5' in message.lower():
            preferences['latest_time'] = '17:00'
        
        if 'no morning' in message.lower() or 'before noon' in message.lower():
            preferences['earliest_time'] = '12:00'
        
        if 'friday' in message.lower() and ('no' in message.lower() or 'free' in message.lower()):
            preferences['exclude_days'] = ['Friday']
        
        if 'monday' in message.lower() and ('no' in message.lower() or 'free' in message.lower()):
            preferences['exclude_days'] = ['Monday']
        
        if 'online' in message.lower():
            preferences['online_only'] = True
        
        if 'minimize gap' in message.lower() or 'back to back' in message.lower():
            preferences['minimize_gaps'] = True
        
        # Check if we need to generate a new schedule
        if preferences:
            # Update preferences
            app_state['preferences'].update(preferences)
            
            # Generate response
            response = f"I'll update your schedule with these preferences: {', '.join(preferences.keys())}."
            
            # Add to chat history
            app_state['chat_history'].append({'role': 'assistant', 'content': response})
            
            return jsonify({
                'status': 'success',
                'response': response,
                'schedule_update': preferences,
                'action': 'generate_new_schedule'
            })
        else:
            # General conversation
            response = "I can help you adjust your schedule. You can tell me things like:\n" \
                      "- 'I want all evenings free'\n" \
                      "- 'No classes on Friday'\n" \
                      "- 'I prefer online classes'\n" \
                      "- 'Minimize gaps between classes'"
            
            app_state['chat_history'].append({'role': 'assistant', 'content': response})
            
            return jsonify({
                'status': 'success',
                'response': response
            })
    
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)