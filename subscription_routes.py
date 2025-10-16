# subscription_routes.py
# Save this as: backend/subscription_routes.py

import stripe
import os
import json
from datetime import datetime
from flask import request, jsonify
from models import get_session_context, User
import traceback

# =====================
# STRIPE CONFIG
# =====================
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://main.d2lu8gx2f335fg.amplifyapp.com")

# Price IDs from Stripe Dashboard
PRICE_IDS = {
    "cryptolite_monthly": os.environ.get("PRICE_CRYPTOLITE_MONTHLY"),
    "cryptolite_annual": os.environ.get("PRICE_CRYPTOLITE_ANNUAL"),
    "cryptopro_monthly": os.environ.get("PRICE_CRYPTOPRO_MONTHLY"),
    "cryptopro_annual": os.environ.get("PRICE_CRYPTOPRO_ANNUAL"),
    "cryptomax_monthly": os.environ.get("PRICE_CRYPTOMAX_MONTHLY"),
    "cryptomax_annual": os.environ.get("PRICE_CRYPTOMAX_ANNUAL"),
}

# Map Stripe Price IDs to your plan names
PLAN_MAPPING = {
    "price_cryptolite_monthly": "free",
    "price_cryptolite_annual": "free",
    "price_cryptopro_monthly": "pro",
    "price_cryptopro_annual": "pro",
    "price_cryptomax_monthly": "max",
    "price_cryptomax_annual": "max",
}


# =====================
# HELPER: Get Price ID
# =====================
def get_price_id(plan_key):
    """
    Get actual Stripe Price ID from environment variables
    plan_key examples: 'cryptopro_monthly', 'cryptomax_annual'
    """
    price_id = PRICE_IDS.get(plan_key)
    if not price_id:
        raise ValueError(f"Price ID not configured for {plan_key}")
    return price_id


# =====================
# CREATE CHECKOUT SESSION
# =====================
def create_checkout_session():
    """
    Frontend calls POST /api/create-checkout-session with:
    {
        "user_sub": "cognito-user-id",
        "priceId": "price_XXXXX"
    }
    
    Returns:
    {
        "id": "cs_...",
        "url": "https://checkout.stripe.com/..."
    }
    """
    data = request.json or {}
    user_sub = data.get("user_sub")
    price_id = data.get("priceId")
    
    if not user_sub or not price_id:
        return jsonify({"error": "user_sub and priceId required"}), 400
    
    try:
        with get_session_context() as session:
            user = session.query(User).filter_by(user_sub=user_sub).first()
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            print(f"[STRIPE] Creating checkout for user {user_sub}, price {price_id}")
            
            # Create Stripe checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price": price_id,
                    "quantity": 1
                }],
                mode="subscription",
                success_url=f"{FRONTEND_URL}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{FRONTEND_URL}/subscription",
                customer_email=user.email,
                client_reference_id=user_sub,  # Critical: Stripe stores this for webhook
                metadata={
                    "user_sub": user_sub,
                    "email": user.email,
                    "name": user.name or "Unknown"
                }
            )
            
            print(f"[STRIPE] ✅ Checkout session created: {checkout_session.id}")
            
            return jsonify({
                "id": checkout_session.id,
                "url": checkout_session.url
            }), 200
            
    except stripe.error.CardError as e:
        print(f"[STRIPE] ❌ Card error: {e}")
        return jsonify({"error": "Card declined"}), 400
    except stripe.error.RateLimitError:
        print(f"[STRIPE] ❌ Rate limit exceeded")
        return jsonify({"error": "Too many requests, try again later"}), 429
    except stripe.error.AuthenticationError:
        print(f"[STRIPE] ❌ Authentication failed")
        return jsonify({"error": "Stripe authentication failed"}), 401
    except stripe.error.APIConnectionError:
        print(f"[STRIPE] ❌ Network error connecting to Stripe")
        return jsonify({"error": "Network error, try again"}), 500
    except Exception as e:
        print(f"[STRIPE] ❌ Unexpected error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================
# WEBHOOK HANDLER
# =====================
def handle_stripe_webhook():
    """
    Stripe sends POST to /webhook/stripe with signed events.
    Update user subscription status in database.
    """
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    
    # Verify webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        print(f"[WEBHOOK] ✅ Signature verified: {event['type']}")
    except ValueError as e:
        print(f"[WEBHOOK] ❌ Invalid payload: {e}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        print(f"[WEBHOOK] ❌ Signature verification failed: {e}")
        return jsonify({"error": "Invalid signature"}), 400
    
    try:
        # EVENT 1: Checkout completed (user paid)
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_sub = session.get("client_reference_id")
            
            # Get the price ID from line items
            price_id = None
            if session.get("line_items"):
                price_id = session["line_items"]["data"][0]["price"]["id"]
            
            print(f"[WEBHOOK] 💳 Checkout completed for user: {user_sub}, price: {price_id}")
            
            if user_sub and price_id:
                with get_session_context() as db_session:
                    user = db_session.query(User).filter_by(user_sub=user_sub).first()
                    if user:
                        plan = PLAN_MAPPING.get(price_id, "free")
                        
                        user.subscription_status = "active"
                        user.subscription_plan = plan
                        user.stripe_customer_id = session.get("customer")
                        user.stripe_subscription_id = session.get("subscription")
                        user.subscription_date = datetime.utcnow()
                        user.updated_at = datetime.utcnow()
                        
                        print(f"[WEBHOOK] ✅ User {user_sub} upgraded to plan: {plan}")
                    else:
                        print(f"[WEBHOOK] ⚠️ User not found: {user_sub}")
        
        # EVENT 2: Subscription renewed/updated
        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            customer_id = subscription.get("customer")
            
            print(f"[WEBHOOK] 🔄 Subscription updated for customer: {customer_id}")
            
            with get_session_context() as db_session:
                user = db_session.query(User).filter_by(
                    stripe_customer_id=customer_id
                ).first()
                if user:
                    user.updated_at = datetime.utcnow()
                    print(f"[WEBHOOK] ✅ Updated subscription for user: {user.user_sub}")
        
        # EVENT 3: Subscription cancelled
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            customer_id = subscription.get("customer")
            
            print(f"[WEBHOOK] ❌ Subscription deleted for customer: {customer_id}")
            
            with get_session_context() as db_session:
                user = db_session.query(User).filter_by(
                    stripe_customer_id=customer_id
                ).first()
                if user:
                    user.subscription_status = "cancelled"
                    user.subscription_plan = "free"
                    user.updated_at = datetime.utcnow()
                    print(f"[WEBHOOK] ✅ User {user.user_sub} subscription cancelled")
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        print(f"[WEBHOOK] ❌ Error processing webhook: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# =====================
# GET USER SUBSCRIPTION STATUS
# =====================
def get_user_subscription():
    """
    Frontend can call GET /api/subscription/<user_sub> to check status
    """
    user_sub = request.view_args.get("user_sub")
    
    try:
        with get_session_context() as session:
            user = session.query(User).filter_by(user_sub=user_sub).first()
            if not user:
                return jsonify({"error": "User not found"}), 404
            
            return jsonify({
                "subscription_status": user.subscription_status,
                "subscription_plan": getattr(user, "subscription_plan", "free"),
                "subscription_date": user.subscription_date.isoformat() if hasattr(user, "subscription_date") and user.subscription_date else None,
                "stripe_customer_id": getattr(user, "stripe_customer_id", None)
            }), 200
    except Exception as e:
        print(f"[API] Error fetching subscription: {e}")
        return jsonify({"error": str(e)}), 500


# =====================
# REGISTER ROUTES
# =====================
# =====================
# REGISTER ROUTES
# =====================
def register_subscription_routes(app):
    """
    Call this in your application.py:
    from subscription_routes import register_subscription_routes
    register_subscription_routes(application)
    """
    
    @app.route("/api/create-checkout-session", methods=["POST", "OPTIONS"])
    def create_checkout():
        if request.method == "OPTIONS":
            # Return 200 with empty body for preflight
            return "", 200
        return create_checkout_session()
    
    @app.route("/webhook/stripe", methods=["POST", "OPTIONS"])
    def stripe_webhook():
        if request.method == "OPTIONS":
            return "", 200
        return handle_stripe_webhook()
    
    @app.route("/api/subscription/<user_sub>", methods=["GET", "OPTIONS"])
    def get_subscription(user_sub):
        if request.method == "OPTIONS":
            return "", 200
        return get_user_subscription()
    
    print("[INIT] ✅ Stripe subscription routes registered")