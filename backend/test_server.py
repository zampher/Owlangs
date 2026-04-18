#!/usr/bin/env python3
"""
Simple test server for Flutter frontend
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Owlangs Test Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: Optional[bool] = False

class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user: Optional[dict] = None
    next_url: Optional[str] = None

class UserModel(BaseModel):
    username: str
    email: Optional[str] = None
    role: str = "user"

@app.get("/")
async def root():
    return {"message": "Owlangs Test Server is running!"}

@app.get("/docs")
async def docs():
    return {"message": "API Documentation available at /docs"}

@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Simple login endpoint for testing"""
    if request.username == "admin" and request.password == "password":
        return LoginResponse(
            success=True,
            message="Login successful",
            token="test_token_123",
            user={
                "username": request.username,
                "email": "admin@example.com",
                "role": "admin"
            },
            next_url="/"
        )
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/auth/user")
async def get_current_user():
    """Mock current user endpoint"""
    return {
        "username": "admin",
        "email": "admin@example.com",
        "role": "admin"
    }

@app.get("/auth/user/permissions")
async def get_user_permissions():
    """Mock user permissions endpoint"""
    return {
        "is_admin": True,
        "can_access_admin_settings": True,
        "can_access_glossary_management": True
    }

@app.get("/logout")
async def logout():
    """Mock logout endpoint"""
    return {"message": "Logged out successfully"}

if __name__ == "__main__":
    import uvicorn
    print("Starting Owlangs Test Server...")
    print("Server will be available at: http://localhost:8800")
    print("API Documentation: http://localhost:8800/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)

