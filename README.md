# Instagram Scraper API

A FastAPI-based service that scrapes Instagram profiles and generates business analysis reports.

## Setup Instructions

### 1. Install Dependencies
```bash
pip install fastapi uvicorn playwright pydantic
```

### 2. Set Up Instagram Login Session
Before using the API, you must create a login session:

```bash
python local_workflow.py
```
- Choose option 1 (Login to Instagram)
- Complete the login process in the browser
- The session will be saved automatically

### 3. Start the API Server
```bash
python app.py
```

The API will be available at: `http://localhost:8000`

## API Endpoints

### Core Endpoints

#### 1. Get API Information
- **URL**: `GET /`
- **Description**: Shows welcome message and available endpoints
- **Response**: List of all available API endpoints

#### 2. Create Scraping Task
- **URL**: `POST /api/scrape`
- **Description**: Start a new Instagram profile scraping task
- **Request Body**:
  ```json
  {
    "username": "instagram_username",
    "use_saved_session": true
  }
  ```
- **Response**:
  ```json
  {
    "task_id": "abc12345",
    "queue_id": null,
    "status": "pending",
    "message": "Scraping task created for @username",
    "created_at": "2024-01-01T12:00:00"
  }
  ```

#### 3. Check Task Status
- **URL**: `GET /api/task/{task_id}`
- **Description**: Get current status and progress of a scraping task
- **Response**:
  ```json
  {
    "task_id": "abc12345",
    "queue_id": "xyz789",
    "status": "completed",
    "progress": "Scraping completed successfully",
    "result": {
      "username": "instagram_username",
      "queue_id": "xyz789",
      "analysis_complete": true,
      "sector": "Technology",
      "competitors_found": 5,
      "timestamp": "2024-01-01T12:30:00"
    },
    "created_at": "2024-01-01T12:00:00",
    "completed_at": "2024-01-01T12:30:00"
  }
  ```

### Login Management

#### 4. Check Login Status
- **URL**: `GET /api/login/status`
- **Description**: Check if Instagram login session exists
- **Response**:
  ```json
  {
    "session_exists": true,
    "session_file": "playwright_profile/state.json",
    "message": "Login session found"
  }
  ```

#### 5. Create Login Session
- **URL**: `POST /api/login/create`
- **Description**: Get instructions for manual login setup
- **Response**: Instructions for setting up login session

### Task Management

#### 6. List All Tasks
- **URL**: `GET /api/tasks`
- **Description**: Get list of all scraping tasks
- **Response**: Array of all tasks with their current status

#### 7. Delete Task
- **URL**: `DELETE /api/task/{task_id}`
- **Description**: Remove a task from memory
- **Response**: Confirmation message

#### 8. Health Check
- **URL**: `GET /health`
- **Description**: Check if API is running properly
- **Response**: Server health status and active task count

## How to Use the API

### Step 1: Check Login Status
```bash
curl -X GET "http://localhost:8000/api/login/status"
```

### Step 2: Create Scraping Task
```bash
curl -X POST "http://localhost:8000/api/scrape" \
  -H "Content-Type: application/json" \
  -d '{"username": "target_username", "use_saved_session": true}'
```

### Step 3: Monitor Task Progress
```bash
curl -X GET "http://localhost:8000/api/task/abc12345"
```

## Task Status Types

- **pending**: Task created, waiting to start
- **running**: Currently scraping Instagram profile
- **completed**: Scraping finished successfully
- **failed**: An error occurred during scraping

## Important Notes

### Login Requirements
- You must have a valid Instagram account
- Login session must be created before using the API
- Sessions are saved locally and reused automatically

## After queue_id is generated, you can use it to check report status and download the report.
# 1. When completed, check report status
curl -X GET "http://65.0.99.113:8000/api/reports/status/{queue_id}"

# 2. Download the report
curl -X GET "http://65.0.99.113:8000/api/reports/download/{queue_id}"
```
