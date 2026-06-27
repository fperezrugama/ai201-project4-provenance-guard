from flask import Blueprint, request, jsonify
import uuid
from datetime import datetime

bp = Blueprint('submit', __name__, url_prefix='/')

@bp.route('/submit', methods=['POST'])
def submit_content():
    """Submit content for attribution analysis - Hardcoded version"""
    
    # Parse request
    data = request.get_json()
    
    # Validate required fields
    if not data:
        return jsonify({"error": "Invalid request - JSON body required"}), 400
    
    if 'text' not in data or not data['text'].strip():
        return jsonify({"error": "Invalid input - text field required"}), 400
    
    if 'creator_id' not in data or not data['creator_id'].strip():
        return jsonify({"error": "Invalid input - creator_id field required"}), 400
    
    # Generate content_id
    content_id = str(uuid.uuid4())
    
    # Hardcoded response for testing
    response = {
        "content_id": content_id,
        "attribution": "uncertain",
        "confidence": 0.50,
        "label": "🔍 UNCERTAIN - Human Review Recommended",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "appeal_available": True
    }
    
    return jsonify(response), 200

@bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy", "message": "Provenance Guard is running!"}), 200

@bp.route('/', methods=['GET'])
def home():
    return jsonify({
        "message": "Provenance Guard API",
        "endpoints": {
            "/health": "GET - Check if the API is running",
            "/submit": "POST - Submit content for analysis",
            "/log": "GET - View audit log (coming soon)"
        },
        "status": "running"
    })