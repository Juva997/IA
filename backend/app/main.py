from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from . import crud, models, schemas, database, auth

app = FastAPI()


@app.on_event("startup")
def on_startup():
    database.init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    existing = crud.get_user_by_username(db, user.username)
    if existing:
        raise HTTPException(status_code=400, detail="username already exists")
    hashed = auth.get_password_hash(user.password)
    created = crud.create_user(db, user.username, hashed)
    return created


@app.post("/auth/login")
def login(form_data: schemas.UserCreate, db: Session = Depends(database.get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/vocab/", response_model=schemas.VocabItemOut)
def create_vocab(item: schemas.VocabItemCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    return crud.create_vocab(db, item.word, item.translation, item.language)


@app.get("/vocab/", response_model=list[schemas.VocabItemOut])
def list_vocab(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    return crud.list_vocab(db, skip=skip, limit=limit)


@app.get("/users/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
