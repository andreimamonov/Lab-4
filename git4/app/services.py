from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models, schemas
from typing import Optional, Tuple

class ItemService:
    """Сервис для работы с Item (мягкое удаление, пагинация)"""

    @staticmethod
    def create(db: Session, item_data: schemas.ItemCreate, user_id: int) -> models.Item:
        """Создать новый элемент (привязанный к пользователю)"""
        db_item = models.Item(
            user_id=user_id,
            name=item_data.name,
            description=item_data.description,
            status=item_data.status
        )
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def get_active_by_id_and_user(db: Session, item_id: int, user_id: int) -> Optional[models.Item]:
        """Получить активный элемент по ID и пользователю"""
        return db.query(models.Item).filter(
            models.Item.id == item_id,
            models.Item.user_id == user_id,
            models.Item.deleted_at.is_(None)
        ).first()

    @staticmethod
    def get_active_by_id(db: Session, item_id: int) -> Optional[models.Item]:
        """Получить активный элемент по ID (без проверки владельца)"""
        return db.query(models.Item).filter(
            models.Item.id == item_id,
            models.Item.deleted_at.is_(None)
        ).first()

    @staticmethod
    def update(db: Session, db_item: models.Item, update_data: schemas.ItemUpdate) -> models.Item:
        """Частичное обновление элемента (PATCH)"""
        if update_data.name is not None:
            db_item.name = update_data.name
        if update_data.description is not None:
            db_item.description = update_data.description
        if update_data.status is not None:
            db_item.status = update_data.status
        db.commit()
        db.refresh(db_item)
        return db_item

    @staticmethod
    def soft_delete(db: Session, db_item: models.Item) -> None:
        """Мягкое удаление (установить deleted_at)"""
        db_item.deleted_at = func.now()
        db.commit()

    @staticmethod
    def get_active_paginated(db: Session, page: int, limit: int) -> Tuple[list[models.Item], int]:
        """Вернуть список активных элементов (всех пользователей)"""
        query = db.query(models.Item).filter(models.Item.deleted_at.is_(None))
        total = query.count()
        items = query.order_by(models.Item.id.desc()) \
                     .offset((page - 1) * limit) \
                     .limit(limit) \
                     .all()
        return items, total

    @staticmethod
    def get_active_paginated_by_user(db: Session, user_id: int, page: int, limit: int) -> Tuple[list[models.Item], int]:
        """Вернуть список активных элементов ТОЛЬКО ДЛЯ КОНКРЕТНОГО ПОЛЬЗОВАТЕЛЯ"""
        query = db.query(models.Item).filter(
            models.Item.user_id == user_id,
            models.Item.deleted_at.is_(None)
        )
        total = query.count()
        items = query.order_by(models.Item.id.desc()) \
                     .offset((page - 1) * limit) \
                     .limit(limit) \
                     .all()
        return items, total