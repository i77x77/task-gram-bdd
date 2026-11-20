from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CameraRecord
from app.security import require_app_password

Difficulty = Literal["easy", "normal", "hard"]
router = APIRouter(prefix="/camera-records", tags=["camera-game"])


class Record(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    score: int = Field(ge=1, le=1_000_000)


@router.get("/{difficulty}", response_model=list[Record])
def list_records(difficulty: Difficulty, db: Session = Depends(get_db)):
    query = (
        select(CameraRecord)
        .where(CameraRecord.difficulty == difficulty)
        .order_by(CameraRecord.score.desc(), CameraRecord.name)
        .limit(10)
    )
    return db.scalars(query).all()


@router.post("/{difficulty}", response_model=list[Record], dependencies=[Depends(require_app_password)])
def save_record(difficulty: Difficulty, body: Record, db: Session = Depends(get_db)):
    statement = insert(CameraRecord).values(difficulty=difficulty, name=body.name, score=body.score)
    db.execute(statement.on_conflict_do_update(
        index_elements=[CameraRecord.difficulty, CameraRecord.name],
        set_={"score": statement.excluded.score},
        where=statement.excluded.score > CameraRecord.score,
    ))
    db.commit()
    return list_records(difficulty, db)
