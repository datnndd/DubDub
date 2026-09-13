import uuid
import time
from fastapi import APIRouter

from core.db import db_conn
from core import event_bus
from schemas.requests import ExportRecordRequest

router = APIRouter()


@router.post("/export/record")
def record_export(req: ExportRecordRequest):
    export_id = str(uuid.uuid4())[:8]
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO export_history (id, filename, destination_path, mode, created_at) VALUES (?, ?, ?, ?, ?)",
            (export_id, req.filename, req.destination_path, req.mode, time.time()),
        )
    event_bus.emit("export_history", {"action": "recorded", "id": export_id})
    return {"success": True, "id": export_id}


@router.get("/export/history")
def get_export_history():
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM export_history ORDER BY created_at DESC LIMIT 50").fetchall()
    return [dict(r) for r in rows]

