"""
Payment integration using Stripe for Voice Assistant subscriptions.
Handles subscription plans, payment processing, and premium access.
"""

import os
import stripe
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from auth import get_user_by_id, save_users, load_users

# Stripe Configuration
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# Subscription Plans
PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'commands_per_day': 100,
        'features': ['Basic voice commands', '100 commands per day', 'No desktop automation']
    },
    'premium_monthly': {
        'name': 'Premium Monthly',
        'price': 9.99,
        'stripe_price_id': os.environ.get('STRIPE_PRICE_MONTHLY', ''),
        'commands_per_day': -1,  # Unlimited
        'features': ['Unlimited commands', 'Desktop automation', 'Priority support', 'Voice search']
    },
    'premium_yearly': {
        'name': 'Premium Yearly',
        'price': 99.99,
        'stripe_price_id': os.environ.get('STRIPE_PRICE_YEARLY', ''),
        'commands_per_day': -1,  # Unlimited
        'features': ['Unlimited commands', 'Desktop automation', 'Priority support', 'Voice search', 'Save 17%']
    }
}

def get_plans():
    """Get available subscription plans."""
    return {
        "plans": PLANS,
        "publishable_key": STRIPE_PUBLISHABLE_KEY
    }

def create_checkout_session(plan_id):
    """Create a Stripe checkout session for subscription."""
    if not STRIPE_SECRET_KEY:
        return None, "Stripe not configured"
    
    plan = PLANS.get(plan_id)
    if not plan or not plan.get('stripe_price_id'):
        return None, "Invalid plan"
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': plan['stripe_price_id'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=request.host_url + 'payment/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url + 'payment/cancel',
        )
        return session, None
    except Exception as e:
        return None, str(e)

def handle_webhook(event):
    """Handle Stripe webhook events."""
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe not configured"}, 500
    
    try:
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            customer_email = session.get('customer_details', {}).get('email')
            
            if customer_email:
                # Find user by email and upgrade to premium
                users_data = load_users()
                for user in users_data['users']:
                    if user['email'] == customer_email:
                        user['is_premium'] = True
                        user['subscription_id'] = session.get('subscription')
                        user['premium_since'] = event['created']
                        save_users(users_data)
                        break
        
        return {"success": True}, 200
    except Exception as e:
        return {"error": str(e)}, 400

def verify_payment_session(session_id):
    """Verify a completed payment session."""
    if not STRIPE_SECRET_KEY:
        return False, "Stripe not configured"
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            return True, session
        return False, "Payment not completed"
    except Exception as e:
        return False, str(e)

def cancel_subscription(user_id):
    """Cancel user's subscription."""
    if not STRIPE_SECRET_KEY:
        return False, "Stripe not configured"
    
    user = get_user_by_id(user_id)
    if not user or not user.get('subscription_id'):
        return False, "No active subscription"
    
    try:
        stripe.Subscription.delete(user['subscription_id'])
        
        # Update user status
        users_data = load_users()
        for u in users_data['users']:
            if u['id'] == user_id:
                u['is_premium'] = False
                u['subscription_id'] = None
                save_users(users_data)
                return True, "Subscription cancelled"
        
        return False, "User not found"
    except Exception as e:
        return False, str(e)
