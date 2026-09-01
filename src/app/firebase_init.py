import os
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore, storage
from app.config import get_settings

_app: Optional[firebase_admin.App] = None

def initialize_firebase(project_id: Optional[str] = None, storage_bucket: Optional[str] = None) -> firebase_admin.App:
    global _app
    if _app is not None and firebase_admin._apps:
        return _app

    settings = get_settings()
    proj = project_id or settings.GCP_PROJECT_ID
    bucket_name = storage_bucket or settings.GCS_BUCKET

    options = {}
    if proj:
        options["projectId"] = proj
    if bucket_name:
        options["storageBucket"] = bucket_name

    if firebase_admin._apps:
        _app = firebase_admin.get_app()
        return _app

    _app = firebase_admin.initialize_app(options=options if options else None)
    return _app

def get_firestore_client(project_id: Optional[str] = None):
    initialize_firebase(project_id=project_id)
    return firestore.client()

def get_storage_bucket(storage_bucket: Optional[str] = None):
    initialize_firebase(storage_bucket=storage_bucket)
    return storage.bucket()
