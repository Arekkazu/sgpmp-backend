from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.identity_access.infrastructure.models.usuarios_model import Usuarios
from src.identity_access.infrastructure.schema.user_schema import UsuarioResponse
from src.shared.database import get_db

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("/", response_model=list[UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db)):
    return db.scalars(select(Usuarios)).all()
