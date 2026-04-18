
#!/usr/bin/env python3
"""
Temporary authentication bypass for development
"""
from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import JSONResponse
from auth.models import User, UserRole
import uvicorn

app = FastAPI()

# Mock user for testing
mock_user = User(
    username="admin",
    display_name="Administrator",
    email="admin@example.com",
    is_authenticated=True,
    role=UserRole.ADMIN
)

@app.get("/api/v1/auth/user")
async def get_current_user(request: Request):
    """Bypass authentication for testing"""
    print("🚨 Using authentication bypass endpoint!")
    return {
        "username": mock_user.username,
        "display_name": mock_user.display_name,
        "email": mock_user.email
    }

@app.get("/api/v1/auth/user/permissions")
async def get_user_permissions(request: Request):
    """Bypass permissions check for testing"""
    print("🚨 Using permissions bypass endpoint!")
    return {
        "is_admin": True,
        "is_super_admin": True,
        "can_access_admin_settings": True,
        "can_access_glossary_management": True,
        "allowed_settings": ["all"],
        "role": "admin"
    }

@app.post("/api/v1/auth/login")
async def login(request: Request, response: Response):
    """Mock login endpoint"""
    print("🚨 Using mock login endpoint!")
    # Set a simple session cookie for testing
    response.set_cookie(
        key="owlangs_session",
        value="test_session",
        httponly=True,
        samesite="lax",
        secure=False
    )
    return {
        "username": mock_user.username,
        "display_name": mock_user.display_name,
        "email": mock_user.email,
        "ok": True
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
