from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
import uuid
import json
import os
from datetime import datetime
from local_workflow import LocalWorkflowController
import threading

app = FastAPI(title="Instagram Scraper API", version="1.0.0")

# In-memory task storage (in production, use Redis or database)
tasks: Dict[str, dict] = {}

class TaskRequest(BaseModel):
    username: str
    use_saved_session: bool = True

class TaskResponse(BaseModel):
    task_id: str
    queue_id: Optional[str] = None  # Add queue_id field
    status: str
    message: str
    created_at: str

class TaskStatus(BaseModel):
    task_id: str
    queue_id: Optional[str] = None  # Add queue_id field
    status: str
    progress: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

def run_scraping_task(task_id: str, username: str, use_saved_session: bool):
    """Background task to run the scraping workflow"""
    try:
        # Update task status to running
        tasks[task_id]["status"] = "running"
        tasks[task_id]["progress"] = "Starting scraping process..."
        
        controller = LocalWorkflowController()
        
        if use_saved_session:
            # Check if saved session exists
            if not controller.check_saved_session():
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "No saved login session found. Please login first."
                return
            
            tasks[task_id]["progress"] = "Using saved session to scrape profile..."
            result = controller.run_local_workflow(username)
        else:
            tasks[task_id]["progress"] = "Manual login required..."
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = "Manual login not supported in API mode. Please use saved session."
            return
        
        if result:
            # Extract queue_id from the result
            queue_id = result.get('queue_id', None)
            tasks[task_id]["queue_id"] = queue_id  # Store queue_id in task
            
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["result"] = {
                "username": username,
                "queue_id": queue_id,
                "analysis_complete": True,
                "sector": result.get('sector_analysis', {}).get('sector', 'Unknown'),
                "competitors_found": len(result.get('competitors', [])),
                "timestamp": result.get('timestamp')
            }
            tasks[task_id]["completed_at"] = datetime.now().isoformat()
            tasks[task_id]["progress"] = f"Scraping completed successfully - Queue ID: {queue_id}"
        else:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = "Scraping failed - check logs for details"
            
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

@app.get("/")
async def root():
    return {
        "message": "Instagram Scraper API",
        "endpoints": {
            "create_task": "/api/scrape",
            "task_status": "/api/task/{task_id}",
            "login_status": "/api/login/status",
            "health": "/health"
        }
    }

@app.post("/api/scrape", response_model=TaskResponse)
async def create_scraping_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Create a new scraping task"""
    task_id = str(uuid.uuid4())[:8]  # Short task ID
    
    # Initialize task
    tasks[task_id] = {
        "task_id": task_id,
        "queue_id": None,  # Will be populated when workflow starts
        "username": request.username,
        "status": "pending",
        "progress": "Task created, waiting to start...",
        "created_at": datetime.now().isoformat(),
        "use_saved_session": request.use_saved_session
    }
    
    # Add background task
    background_tasks.add_task(
        run_scraping_task, 
        task_id, 
        request.username, 
        request.use_saved_session
    )
    
    return TaskResponse(
        task_id=task_id,
        queue_id=None,  # Queue ID not available yet
        status="pending",
        message=f"Scraping task created for @{request.username}",
        created_at=tasks[task_id]["created_at"]
    )

@app.get("/api/task/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """Get task status and results"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    return TaskStatus(**task)

@app.get("/api/login/status")
async def check_login_status():
    """Check if Instagram login session exists"""
    controller = LocalWorkflowController()
    session_exists = controller.check_saved_session()
    
    return {
        "session_exists": session_exists,
        "session_file": "playwright_profile/state.json",
        "message": "Login session found" if session_exists else "No login session found - manual login required"
    }

@app.post("/api/login/create")
async def create_login_session():
    """Trigger manual login process (requires manual browser interaction)"""
    controller = LocalWorkflowController()
    
    # Check if session already exists
    if controller.check_saved_session():
        return {
            "status": "success",
            "message": "Login session already exists",
            "action_required": False
        }
    
    return {
        "status": "manual_action_required",
        "message": "Please run 'python local_workflow.py' and choose option 1 to login manually",
        "instructions": [
            "1. Run: python local_workflow.py",
            "2. Choose option 1 (Login to Instagram)",
            "3. Complete login in browser",
            "4. Close browser when done",
            "5. Session will be saved automatically"
        ]
    }

@app.get("/api/tasks")
async def list_all_tasks():
    """List all tasks with their current status"""
    return {
        "tasks": list(tasks.values()),
        "total_tasks": len(tasks)
    }

@app.delete("/api/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task from memory"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del tasks[task_id]
    return {"message": f"Task {task_id} deleted successfully"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_tasks": len([t for t in tasks.values() if t["status"] == "running"])
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)