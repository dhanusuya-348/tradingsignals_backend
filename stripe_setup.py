# stripe_setup.py
# Run this ONCE to create Stripe products and prices
# Save as: stripe_setup.py (in your project root)
# Then run: python stripe_setup.py

import stripe
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set your Stripe test key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

if not stripe.api_key:
    print("❌ ERROR: STRIPE_SECRET_KEY not found in .env")
    exit(1)

print(f"[INFO] Using Stripe API key: {stripe.api_key[:20]}...")

# Define your plans (matching your frontend images)
plans = [
    {
        "name": "CryptoLite",
        "description": "Perfect for beginners exploring crypto signals",
        "monthly_amount": 0,      # Free tier
        "annual_amount": 0        # Free tier
    },
    {
        "name": "CryptoPro",
        "description": "Ideal for regular traders wanting broader coverage",
        "monthly_amount": 4900,   # $49.00/month
        "annual_amount": 49000    # $490.00/year (20% discount from 12*49)
    },
    {
        "name": "CryptoMax",
        "description": "Complete access for power users",
        "monthly_amount": 14900,  # $149.00/month
        "annual_amount": 149000   # $1490.00/year (20% discount from 12*149)
    }
]

# Store all price IDs here
price_ids = {}

try:
    for plan in plans:
        print(f"\n{'='*60}")
        print(f"Creating: {plan['name']}")
        print(f"{'='*60}")
        
        # Step 1: Create Product
        product = stripe.Product.create(
            name=plan["name"],
            description=plan["description"],
            type="service"
        )
        product_id = product.id
        print(f"✅ Product created: {product_id}")
        
        # Step 2: Create Monthly Price
        if plan["monthly_amount"] > 0:
            price_monthly = stripe.Price.create(
                unit_amount=plan["monthly_amount"],
                currency="usd",
                recurring={"interval": "month"},
                product=product_id
            )
            price_monthly_id = price_monthly.id
            monthly_price = plan["monthly_amount"] / 100
            print(f"✅ Monthly price created: {price_monthly_id} (${monthly_price}/month)")
            price_ids[f"{plan['name'].lower()}_monthly"] = price_monthly_id
        else:
            # For free tier, still create a price but with 0 amount
            price_monthly = stripe.Price.create(
                unit_amount=0,
                currency="usd",
                recurring={"interval": "month"},
                product=product_id
            )
            price_monthly_id = price_monthly.id
            print(f"✅ Monthly price created (FREE): {price_monthly_id}")
            price_ids[f"{plan['name'].lower()}_monthly"] = price_monthly_id
        
        # Step 3: Create Annual Price
        if plan["annual_amount"] > 0:
            price_annual = stripe.Price.create(
                unit_amount=plan["annual_amount"],
                currency="usd",
                recurring={"interval": "year"},
                product=product_id
            )
            price_annual_id = price_annual.id
            annual_price = plan["annual_amount"] / 100
            print(f"✅ Annual price created: {price_annual_id} (${annual_price}/year)")
            price_ids[f"{plan['name'].lower()}_annual"] = price_annual_id
        else:
            # For free tier
            price_annual = stripe.Price.create(
                unit_amount=0,
                currency="usd",
                recurring={"interval": "year"},
                product=product_id
            )
            price_annual_id = price_annual.id
            print(f"✅ Annual price created (FREE): {price_annual_id}")
            price_ids[f"{plan['name'].lower()}_annual"] = price_annual_id

    # Print summary
    print(f"\n{'='*60}")
    print("✅ ALL STRIPE PRODUCTS & PRICES CREATED SUCCESSFULLY!")
    print(f"{'='*60}")
    print("\n📋 Add these to your .env file:\n")
    
    env_content = """
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET_HERE

# Price IDs - Copy from output below:
"""
    
    for key, value in price_ids.items():
        env_key = f"PRICE_{key.upper()}"
        env_content += f"\n{env_key}={value}"
    
    env_content += "\n\nFRONTEND_URL=https://www.dollaraptor.com\n"
    
    print(env_content)
    
    # Save to a file for reference
    with open("stripe_env_output.txt", "w") as f:
        f.write(env_content)
    print("\n💾 Also saved to: stripe_env_output.txt")

except stripe.error.CardError as e:
    print(f"❌ Card error: {e}")
except stripe.error.RateLimitError:
    print(f"❌ Rate limit exceeded")
except stripe.error.AuthenticationError:
    print(f"❌ Authentication failed - check your API key")
except stripe.error.APIConnectionError:
    print(f"❌ Network error connecting to Stripe")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()