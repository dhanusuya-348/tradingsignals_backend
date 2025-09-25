"""
Environment variable loader for .env file
"""

import os
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file"""
    
    # Find .env file in project root
    env_file = Path(__file__).parent / '.env'
    
    if not env_file.exists():
        print(f".env file not found at {env_file}")
        return False
    
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value
        
        print(f"Loaded environment variables from {env_file}")
        
        # Verify DATABASE_URL is loaded
        if 'DATABASE_URL' in os.environ:
            db_url = os.environ['DATABASE_URL']
            # Mask password in log
            if '@' in db_url:
                masked_url = db_url.split('@')[0].split(':')[:-1]
                masked_url = ':'.join(masked_url) + ':***@' + db_url.split('@')[1]
                print(f"DATABASE_URL loaded: {masked_url}")
            else:
                print("DATABASE_URL loaded")
        else:
            print("DATABASE_URL not found in .env file")
        
        return True
        
    except Exception as e:
        print(f"Error loading .env file: {e}")
        return False

# Auto-load when imported
if __name__ != "__main__":
    load_env_file()

# Test function
if __name__ == "__main__":
    print("Testing .env loader...")
    success = load_env_file()
    
    if success:
        print("\nEnvironment variables loaded:")
        for key in ['DATABASE_URL', 'AWS_REGION', 'BINANCE_API_KEY']:
            value = os.environ.get(key, 'Not set')
            if 'URL' in key or 'KEY' in key:
                # Mask sensitive values
                if value != 'Not set' and len(value) > 10:
                    value = value[:10] + "***"
            print(f"  {key}: {value}")
    else:
        print("Failed to load .env file")