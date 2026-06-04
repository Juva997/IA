from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True


class VocabItemCreate(BaseModel):
    word: str
    translation: str
    language: str = 'pt-en'


class Token(BaseModel):
    access_token: str
    token_type: str


class VocabItemOut(BaseModel):
    id: int
    word: str
    translation: str
    language: str

    class Config:
        orm_mode = True
