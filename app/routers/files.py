from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Task
from app.services.auth import get_current_user
from app.services.s3 import upload_file_to_s3, get_presigned_url, delete_file_from_s3
from app.config import settings

router = APIRouter()


@router.post("/{task_id}/upload")
async def upload_attachment(
    task_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.owner_id == current_user.id,
            Task.is_deleted == False,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    # Borrar adjunto anterior si existe
    if task.s3_attachment_key:
        delete_file_from_s3(task.s3_attachment_key)

    result = await upload_file_to_s3(file, current_user.id, task_id)
    task.s3_attachment_key = result["key"]
    task.attachment_filename = result["filename"]
    db.commit()

    return {"message": "Archivo subido correctamente", "filename": result["filename"]}


@router.get("/{task_id}/download-url")
def get_download_url(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.owner_id == current_user.id,
        )
        .first()
    )
    if not task or not task.s3_attachment_key:
        raise HTTPException(status_code=404, detail="No hay adjunto para esta tarea")

    url = get_presigned_url(task.s3_attachment_key)
    if not url:
        raise HTTPException(status_code=503, detail="No se pudo generar la URL")

    return {"url": url, "filename": task.attachment_filename, "expires_in": 3600}


@router.delete("/{task_id}/attachment", status_code=204)
def delete_attachment(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.owner_id == current_user.id,
        )
        .first()
    )
    if not task or not task.s3_attachment_key:
        raise HTTPException(status_code=404, detail="No hay adjunto")

    delete_file_from_s3(task.s3_attachment_key)
    task.s3_attachment_key = None
    task.attachment_filename = None
    db.commit()
