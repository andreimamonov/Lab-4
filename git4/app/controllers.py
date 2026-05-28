from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app import services, schemas
from app.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/items", tags=["Items"])

# ---- GET /items (список с пагинацией) ----
@router.get(
    "/",
    response_model=schemas.PaginatedResponse,
    summary="Получить список всех items",
    description="Возвращает список всех активных (не удалённых) items с пагинацией. Доступно только авторизованным пользователям.",
    responses={
        200: {"description": "Успешный ответ", "content": {"application/json": {"example": {
            "data": [{"id": 1, "name": "Ноутбук", "description": "Игровой ноутбук", "status": "active", "user_id": 1, "created_at": "2026-05-26T10:00:00Z", "updated_at": "2026-05-26T10:00:00Z"}],
            "meta": {"total": 1, "page": 1, "limit": 10, "total_pages": 1}
        }}}},
        401: {"description": "Не авторизован", "content": {"application/json": {"example": {"detail": "Not authenticated"}}}}
    }
)
def get_items(
    page: int = Query(1, ge=1, description="Номер страницы (начиная с 1)"),
    limit: int = Query(10, ge=1, le=100, description="Количество записей на странице (макс. 100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items, total = services.ItemService.get_active_paginated_by_user(db, current_user.id, page, limit)
    total_pages = (total + limit - 1) // limit

    return {
        "data": [schemas.ItemResponse.model_validate(item) for item in items],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }
    }

# ---- GET /items/{id} (получить один элемент) ----
@router.get(
    "/{item_id}",
    response_model=schemas.ItemResponse,
    summary="Получить item по ID",
    description="Возвращает один item по его ID. Только если item принадлежит текущему пользователю.",
    responses={
        200: {"description": "Успешный ответ", "content": {"application/json": {"example": {
            "id": 1, "name": "Ноутбук", "description": "Игровой ноутбук", "status": "active", "user_id": 1, "created_at": "2026-05-26T10:00:00Z", "updated_at": "2026-05-26T10:00:00Z"
        }}}},
        401: {"description": "Не авторизован"},
        404: {"description": "Item не найден", "content": {"application/json": {"example": {"detail": "Item not found"}}}}
    }
)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = services.ItemService.get_active_by_id_and_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

# ---- POST /items (создать) ----
@router.post(
    "/",
    response_model=schemas.ItemResponse,
    status_code=201,
    summary="Создать новый item",
    description="Создаёт новый item, привязанный к текущему авторизованному пользователю.",
    responses={
        201: {"description": "Item успешно создан", "content": {"application/json": {"example": {
            "id": 1, "name": "Новый предмет", "description": "Описание", "status": "active", "user_id": 1, "created_at": "2026-05-26T10:00:00Z", "updated_at": "2026-05-26T10:00:00Z"
        }}}},
        401: {"description": "Не авторизован"},
        422: {"description": "Ошибка валидации", "content": {"application/json": {"example": {"detail": [{"loc": ["body", "name"], "msg": "field required", "type": "value_error"}]}}}}
    }
)
def create_item(
    item_data: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return services.ItemService.create(db, item_data, current_user.id)

# ---- PUT /items/{id} (полное обновление) ----
@router.put(
    "/{item_id}",
    response_model=schemas.ItemResponse,
    summary="Полное обновление item",
    description="Заменяет все поля item новыми значениями. Требует передачи всех полей.",
    responses={
        200: {"description": "Item успешно обновлён"},
        401: {"description": "Не авторизован"},
        404: {"description": "Item не найден"}
    }
)
def update_item_full(
    item_id: int,
    item_data: schemas.ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = services.ItemService.get_active_by_id_and_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.name = item_data.name
    item.description = item_data.description
    item.status = item_data.status
    db.commit()
    db.refresh(item)
    return item

# ---- PATCH /items/{id} (частичное обновление) ----
@router.patch(
    "/{item_id}",
    response_model=schemas.ItemResponse,
    summary="Частичное обновление item",
    description="Обновляет только переданные поля item. Остальные остаются без изменений.",
    responses={
        200: {"description": "Item успешно обновлён"},
        401: {"description": "Не авторизован"},
        404: {"description": "Item не найден"}
    }
)
def update_item_partial(
    item_id: int,
    item_data: schemas.ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = services.ItemService.get_active_by_id_and_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    updated = services.ItemService.update(db, item, item_data)
    return updated

# ---- DELETE /items/{id} (мягкое удаление) ----
@router.delete(
    "/{item_id}",
    status_code=204,
    summary="Мягкое удаление item",
    description="Помечает item как удалённый (заполняет поле deleted_at). Item остаётся в БД, но не возвращается в GET запросах.",
    responses={
        204: {"description": "Item успешно удалён (мягко)"},
        401: {"description": "Не авторизован"},
        404: {"description": "Item не найден"}
    }
)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = services.ItemService.get_active_by_id_and_user(db, item_id, current_user.id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    services.ItemService.soft_delete(db, item)
    return None