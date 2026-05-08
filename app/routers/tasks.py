from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.database import get_db
from app.models import Task, User, Status, Priority
from app.schemas import TaskCreate, TaskUpdate, TaskOut, TaskStats
from app.services.auth import get_current_user

router = APIRouter()


def get_task_or_404(task_id: int, user: User, db: Session) -> Task:
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.owner_id == user.id,
            Task.is_deleted == False,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return task


@router.get("/", response_model=List[TaskOut])
def list_tasks(
    status: Optional[Status] = Query(None),
    priority: Optional[Priority] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Task).filter(
        Task.owner_id == current_user.id,
        Task.is_deleted == False,
    )
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if search:
        query = query.filter(Task.title.ilike(f"%{search}%"))

    return query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/stats", response_model=TaskStats)
def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base = db.query(Task).filter(
        Task.owner_id == current_user.id, Task.is_deleted == False
    )
    return TaskStats(
        total=base.count(),
        todo=base.filter(Task.status == Status.TODO).count(),
        in_progress=base.filter(Task.status == Status.IN_PROGRESS).count(),
        done=base.filter(Task.status == Status.DONE).count(),
        archived=base.filter(Task.status == Status.ARCHIVED).count(),
        high_priority=base.filter(
            Task.priority.in_([Priority.HIGH, Priority.URGENT])
        ).count(),
    )


@router.post("/", response_model=TaskOut, status_code=201)
def create_task(
    task_data: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = Task(**task_data.model_dump(), owner_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_task_or_404(task_id, current_user, db)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    updates: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = get_task_or_404(task_id, current_user, db)
    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = get_task_or_404(task_id, current_user, db)
    task.is_deleted = True  # soft delete — resiliencia
    db.commit()


@router.post("/{task_id}/restore", response_model=TaskOut)
def restore_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.owner_id == current_user.id,
            Task.is_deleted == True,
        )
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Tarea eliminada no encontrada")
    task.is_deleted = False
    db.commit()
    db.refresh(task)
    return task
