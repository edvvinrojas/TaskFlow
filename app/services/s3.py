import boto3
import uuid
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import UploadFile, HTTPException
from app.config import settings

logger = logging.getLogger("taskflow.s3")


def get_s3_client():
    try:
        return boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    except Exception as e:
        logger.error(f"Error creando cliente S3: {e}")
        return None


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".txt", ".docx", ".xlsx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def upload_file_to_s3(file: UploadFile, user_id: int, task_id: int) -> dict:
    """Sube un archivo a S3 y retorna la key y URL prefirmada."""
    if not settings.S3_BUCKET_NAME:
        raise HTTPException(status_code=503, detail="S3 no configurado")

    import os

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=f"Tipo de archivo no permitido: {ext}"
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, detail="Archivo demasiado grande (máx 10MB)"
        )

    s3_key = f"users/{user_id}/tasks/{task_id}/{uuid.uuid4()}{ext}"

    client = get_s3_client()
    if not client:
        raise HTTPException(status_code=503, detail="No se pudo conectar a S3")

    try:
        client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=content,
            ContentType=file.content_type,
            ServerSideEncryption="AES256",
        )
        logger.info(f"Archivo subido a S3: {s3_key}")
        return {"key": s3_key, "filename": file.filename}
    except ClientError as e:
        logger.error(f"Error subiendo a S3: {e}")
        raise HTTPException(status_code=500, detail="Error al subir archivo")


def get_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """Genera URL prefirmada para descarga."""
    client = get_s3_client()
    if not client or not settings.S3_BUCKET_NAME:
        return None
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expiration,
        )
        return url
    except ClientError as e:
        logger.error(f"Error generando URL prefirmada: {e}")
        return None


def delete_file_from_s3(s3_key: str) -> bool:
    """Elimina un archivo de S3."""
    client = get_s3_client()
    if not client or not settings.S3_BUCKET_NAME:
        return False
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        logger.info(f"Archivo eliminado de S3: {s3_key}")
        return True
    except ClientError as e:
        logger.error(f"Error eliminando de S3: {e}")
        return False
