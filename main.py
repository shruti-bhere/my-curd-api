import sqlite3
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel

DB_NAME = "tasks.db"

# --- Database Helper Functions ---

def get_db():
    """Returns a SQLite connection with dict-like row access."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the tasks table and seeds 3 initial tasks if empty."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Create table if missing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        
        # 2. Check row count and seed ONLY if table is completely empty
        cursor.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        
        if count == 0:
            seed_tasks = [
                ("Learn SQLite parameterized queries", 0),
                ("Build FastAPI CRUD endpoints", 1),
                ("Inspect database in DB Browser", 0)
            ]
            cursor.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)", 
                seed_tasks
            )
            conn.commit()

# --- Application Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema and seed on startup
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

# --- Request / Response Models ---

class TaskCreate(BaseModel):
    title: str
    done: Optional[bool] = False

class TaskUpdate(BaseModel):
    title: str
    done: bool

# --- API Endpoints ---

@app.get("/tasks")
def get_tasks():
    """Stage 1: Fetch all tasks from SQLite."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, done FROM tasks")
        rows = cursor.fetchall()
        return [
            {"id": row["id"], "title": row["title"], "done": bool(row["done"])}
            for row in rows
        ]

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Stage 1: Fetch single task by ID using parameterized query."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, done FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Task not found"
            )
            
        return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    """Stage 2: Insert new task into database."""
    clean_title = task.title.strip()
    if not clean_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Title cannot be empty"
        )
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            (clean_title, int(task.done))
        )
        conn.commit()
        new_id = cursor.lastrowid
        
    return {"id": new_id, "title": clean_title, "done": task.done}

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    """Stage 3: Update existing task."""
    clean_title = task.title.strip()
    if not clean_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Title cannot be empty"
        )
        
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (clean_title, int(task.done), task_id)
        )
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Task not found"
            )
            
    return {"id": task_id, "title": clean_title, "done": task.done}

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    """Stage 3: Delete task by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Task not found"
            )
            
    return Response(status_code=status.HTTP_204_NO_CONTENT)