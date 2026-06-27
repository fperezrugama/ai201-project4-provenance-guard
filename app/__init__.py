from flask import Flask, jsonify
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-for-testing')

    # Initialize rate limiter (limits are declared per-route; see routes/submit.py)
    from app.extensions import limiter
    limiter.init_app(app)

    # Return a JSON 429 (instead of the default HTML) to stay consistent with
    # the rest of the API.
    @app.errorhandler(429)
    def ratelimit_exceeded(error):
        return jsonify({
            "error": "Rate limit exceeded. Please try again later.",
            "detail": str(error.description),
        }), 429

    # Register blueprints
    from app.routes import submit, dashboard, analytics, certificate
    app.register_blueprint(submit.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(certificate.bp)

    return app