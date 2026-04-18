
#!/usr/bin/env python3
"""
Fixed run script for Owlangs backend
Disables Redis dependency for authentication
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Disable Redis for session management
os.environ["REDIS_ENABLED"] = "false"
print("🚫 Redis disabled for session management")
print("🔄 Using in-memory session storage fallback")

# Import the pre-created app instance
from app.factory import app
from uvicorn import run

def main():
    """Run the application"""
    # Run with uvicorn using the pre-created app instance
    print("🚀 Starting Owlangs backend server")
    print("📝 Access at: http://localhost:8800")
    print("🔧 API docs: http://localhost:8800/docs")
    
    run(
        app,
        host="0.0.0.0",
        port=8800,
        reload=False
    )

if __name__ == "__main__":
    main()
