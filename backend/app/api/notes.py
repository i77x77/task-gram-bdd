from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Note
from app.schemas import NoteCreate, NoteOut, NoteUpdate
from app.services.tasks import NotFound

router = APIRouter(prefix="/notes", tags=["notes"])


def _get(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if not note:
        raise NotFound(f"note {note_id}")
    return note


@router.get("", response_model=list[NoteOut])
def list_notes(db: Session = Depends(get_db)):
    return db.scalars(select(Note).order_by(Note.updated_at.desc(), Note.id.desc())).all()


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(body: NoteCreate, db: Session = Depends(get_db)):
    note = Note(title=body.title.strip(), text=body.text, author_name=(body.author_name or "").strip() or None)
    db.add(note)
    db.commit()
    return note


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db)):
    note = _get(db, note_id)
    if body.title is not None:
        note.title = body.title.strip()
    if body.text is not None:
        note.text = body.text
    db.commit()
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, note_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
