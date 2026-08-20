"""Caso de uso: listado paginado de usuarios con filtros opcionales.

Soporta filtro por nombre, correo, estado de cuenta y rol. La página máxima
es de 50 ítems para proteger el rendimiento de la consulta.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.domain.repositories.evento_repository import EventoRepository
from src.identity_access.domain.repositories.usuario_repository import UsuarioRepository
from src.identity_access.infrastructure.dependencies import UsuarioActual

TIPO_CONSULTA_LISTA_USUARIOS = 17


class ListarUsuariosUseCase:
    """Orquesta la consulta paginada de usuarios con filtros y auditoría."""

    def __init__(
        self,
        usuarios_repo: UsuarioRepository,
        eventos_repo: EventoRepository,
        db: Session,
    ):
        """Inicializa el use case.

        Args:
            usuarios_repo: Repositorio de dominio del agregado Usuario (conteo y proyección de lectura).
            eventos_repo: Repositorio de dominio de eventos (registro de auditoría).
            db: Sesión SQLAlchemy activa del request.
        """
        self.usuarios_repo = usuarios_repo
        self.eventos_repo = eventos_repo
        self.db = db

    def execute(
        self,
        usuario_actual: UsuarioActual,
        nombre: Optional[str],
        correo: Optional[str],
        id_estado: Optional[int],
        id_rol: Optional[int],
        pagina: int,
        tamano: int,
        estado_cuenta: Optional[str] = None,
        actualizado_desde: Optional[datetime] = None,
    ) -> dict:
        """Retorna la página de usuarios que coinciden con los filtros.

        Args:
            usuario_actual: Administrador que realiza la consulta.
            nombre: Filtro parcial por nombre de usuario.
            correo: Filtro parcial por correo electrónico.
            id_estado: Filtro exacto por id de estado de cuenta.
            id_rol: Filtro exacto por rol.
            pagina: Número de página (base 1).
            tamano: Cantidad de ítems por página (máximo efectivo: 50).
            estado_cuenta: Filtro exacto por nombre de estado de cuenta
                (case-insensitive), alternativa a `id_estado` que no requiere
                conocer el id numérico del catálogo.
            actualizado_desde: Si se indica, solo retorna usuarios modificados
                (dato propio o estado de cuenta) desde ese instante — soporta
                el refresco incremental de la vista de administración.

        Returns:
            Diccionario con `total`, `pagina`, `tamano`, `mensaje` e `items`
            (lista de
            :class:`~src.identity_access.domain.entities.usuario_detalle.UsuarioDetalle`).
        """
        tamano = min(tamano, 50)
        offset = (pagina - 1) * tamano

        total = self.usuarios_repo.contar(
            nombre, correo, id_estado, id_rol, estado_cuenta, actualizado_desde
        )
        items = self.usuarios_repo.listar_detalle(
            nombre, correo, id_estado, id_rol, offset, tamano, estado_cuenta, actualizado_desde
        )

        mensaje: Optional[str] = None
        if total == 0:
            mensaje = (
                "No hay usuarios modificados desde la fecha indicada."
                if actualizado_desde is not None
                else "No se encontraron usuarios que coincidan con los filtros aplicados."
            )

        try:
            self.eventos_repo.registrar(
                tipo_evento=TIPO_CONSULTA_LISTA_USUARIOS,
                exitoso=True,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "filtros": {
                        "nombre": nombre,
                        "correo": correo,
                        "id_estado": id_estado,
                        "id_rol": id_rol,
                        "estado_cuenta": estado_cuenta,
                        "actualizado_desde": (
                            actualizado_desde.isoformat() if actualizado_desde else None
                        ),
                    },
                    "total_resultados": total,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "total": total,
            "pagina": pagina,
            "tamano": tamano,
            "mensaje": mensaje,
            "items": items,
        }
