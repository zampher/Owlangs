#!/usr/bin/env python3
"""
简化的应用启动脚本，不依赖认证模块
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from backend.runtime_version import get_backend_version_tuple

__version__, _ = get_backend_version_tuple()

# Create simplified FastAPI app (version from single source)
app = FastAPI(
    title="Owlangs",
    description="Document Translation Platform",
    version=__version__,
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加静态文件
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def main_page():
    """Serve the main application page."""
    # 检查Vue前端是否可用
    vue_frontend_path = Path(__file__).parent.parent / "vue-frontend" / "dist" / "index.html"
    if vue_frontend_path.exists():
        return FileResponse(vue_frontend_path)
    else:
        # 回退到传统前端
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        else:
            return HTMLResponse("<h1>No frontend available</h1><p>Please build the Vue frontend or check the legacy frontend.</p>")

@app.get("/legacy", response_class=HTMLResponse)
async def legacy_frontend():
    """Serve the legacy frontend."""
    index_path = static_dir / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Legacy frontend not found</h1>")
    return FileResponse(index_path)

@app.get("/select", response_class=HTMLResponse)
async def frontend_selector():
    """Serve the frontend selection page."""
    selector_path = static_dir / "frontend-selector.html"
    if not selector_path.exists():
        return HTMLResponse("<h1>Frontend selector not found</h1>")
    return FileResponse(selector_path)

@app.get("/test")
async def test_route():
    """Test route."""
    return {"message": "Simple app is working!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8800)


