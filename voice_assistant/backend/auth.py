"""
Authentication and user management for Voice Assistant.
Handles user registration, login, JWT tokens, and admin verification.
"""

import os
import json
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
from pathlib import Path

# JWT Configuration
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'your-secret-key-change-this-in-production')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# User storage (in production, use a database)
USERS_FILE = Path(__file__).resolve().parent / "users.json"

# Load users from file
def load_users():
    try:
        if USERS_FILE.exists():
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    # Default admin user
    return {
        "users": [
            {
                "id": "admin",
                "email": "admin@voiceassistant.com",
                "password_hash": bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode(),
                "is_admin": True,
                "is_premium": True,
                "usage_count": 0,
                "created_at": datetime.now().isoformat()
            }
        ]
    }

# Save users to file
def save_users(users_data):
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f, indent=2)

# Get user by email
def get_user_by_email(email):
    users_data = load_users()
    for user in users_data['users']:
        if user['email'] == email:
            return user
    return None

# Get user by ID
def get_user_by_id(user_id):
    users_data = load_users()
    for user in users_data['users']:
        if user['id'] == user_id:
            return user
    return None

# Check if user is admin
def is_admin(user_id):
    user = get_user_by_id(user_id)
    return user and user.get('is_admin', False)

# Check if user has premium access
def has_premium_access(user_id):
    user = get_user_by_id(user_id)
    return user and user.get('is_premium', False)

# Increment user usage
def increment_usage(user_id):
    users_data = load_users()
    for user in users_data['users']:
        if user['id'] == user_id:
            user['usage_count'] = user.get('usage_count', 0) + 1
            user['last_used'] = datetime.now().isoformat()
            save_users(users_data)
            return user['usage_count']
    return 0

# Get user usage
def get_user_usage(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return 0
    return user.get('usage_count', 0)

# Check usage limits (free tier: 100 commands per day)
def check_usage_limit(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    # Admin and premium users have unlimited usage
    if user.get('is_admin', False) or user.get('is_premium', False):
        return True
    
    # Free tier: 100 commands per day
    usage_count = user.get('usage_count', 0)
    FREE_TIER_LIMIT = 100
    
    # Reset daily usage if it's a new day
    last_used = user.get('last_used')
    if last_used:
        last_used_date = datetime.fromisoformat(last_used).date()
        today = datetime.now().date()
        if last_used_date < today:
            # Reset usage for new day
            user['usage_count'] = 0
            users_data = load_users()
            for u in users_data['users']:
                if u['id'] == user_id:
                    u['usage_count'] = 0
            save_users(users_data)
            return True
    
    return usage_count < FREE_TIER_LIMIT

# Decorator to check usage limit
def require_usage_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        if not check_usage_limit(user_id):
            return jsonify({
                "error": "Usage limit exceeded",
                "message": "Free tier limit reached. Please upgrade to premium for unlimited access.",
                "usage_count": get_user_usage(user_id),
                "limit": 100
            }), 429
        return f(*args, **kwargs)
    return decorated_function

# Decorator to check admin access
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        if not is_admin(user_id):
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Initialize JWT manager
def init_jwt(app):
    app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = JWT_ACCESS_TOKEN_EXPIRES
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = JWT_REFRESH_TOKEN_EXPIRES
    return JWTManager(app)
