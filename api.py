from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from uuid import uuid4
import os
from graph import build_graph

app = FastAPI()

# In-memory task storage
TASKS = {}

def run_clause_analysis(task_id: str, file_path: str):
    try:
        app_graph = build_graph()

        result = app_graph.invoke({
            "file_path": file_path
        })

        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["result"] = result.get("final_report")

    except Exception as e:
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["result"] = str(e)


@app.post("/analyze")
async def analyze_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    task_id = str(uuid4())

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{task_id}_{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    TASKS[task_id] = {
        "status": "pending",
        "result": None
    }

    background_tasks.add_task(
        run_clause_analysis,
        task_id,
        file_path
    )

    return {
        "task_id": task_id,
        "status": "processing"
    }


@app.get("/result/{task_id}")
def get_result(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": TASKS[task_id]["status"],
        "result": TASKS[task_id]["result"]
    }

from fastapi.responses import PlainTextResponse

@app.get("/download/{task_id}")
def download_report(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    if TASKS[task_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    return PlainTextResponse(
        TASKS[task_id]["result"],
        headers={
            "Content-Disposition": f"attachment; filename={task_id}_report.md"
        }
    )
