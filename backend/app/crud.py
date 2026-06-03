from sqlalchemy.orm import Session
from . import models


def create_user(db: Session, username: str, hashed_password: str):
    user = models.User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def create_vocab(db: Session, word: str, translation: str, language: str = 'pt-en'):
    item = models.VocabItem(word=word, translation=translation, language=language)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_vocab(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.VocabItem).offset(skip).limit(limit).all()
