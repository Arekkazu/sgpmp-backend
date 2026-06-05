from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.application.ports.auditoria_ports import AuditoriaPort
from src.identity_access.application.ports.sesiones_ports import SesionesPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.identity_access.infrastructure.models.enums_models import EnumEventoResultado
from src.shared.errors import AuthorizationError, ValidationError

ROL_ADMINISTRADOR = 1
TIPO_CONSULTA_AUDITORIA = 16


class ConsultarAuditoriaUseCase:

    def __init__(
        self,
        auditoria_port: AuditoriaPort,
        sesiones_port: SesionesPort,
        db: Session,
    ):
        self.auditoria_port = auditoria_port
        self.sesiones_port = sesiones_port
        self.db = db

    def execute(
        self,
        usuario_actual: UsuarioActual,
        id_usuario: Optional[int],
        tipo_evento: Optional[int],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        pagina: int,
        tamano: int,
    ) -> dict:
        # 1. Solo administradores
        if usuario_actual.id_rol != ROL_ADMINISTRADOR:
            try:
                self.sesiones_port.registrar_evento(
                    tipo_evento=TIPO_CONSULTA_AUDITORIA,
                    resultado=EnumEventoResultado.FALLIDO,
                    id_usuario=usuario_actual.id_usuario,
                    detalle={"razon": "ACCESO_DENEGADO"},
                )
                self.db.commit()
            except Exception:
                self.db.rollback()
            raise AuthorizationError(
                code="ACCESO_DENEGADO",
                message=(
                    "Acceso denegado: No posee privilegios de administrador para consultar "
                    "el historial de auditoría. Este incidente ha sido registrado."
                ),
            )

        # 2. Validar rango de fechas
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ValidationError(
                code="RANGO_FECHAS_INVALIDO",
                message=(
                    "Error de consulta: Los parámetros de filtrado son inconsistentes. "
                    "Verifique el rango de fechas y los identificadores de usuario seleccionados."
                ),
            )

        # 3. Limitar tamaño de página
        tamano = min(tamano, 50)
        offset = (pagina - 1) * tamano

        # 4. Consultar eventos con verificación de integridad
        total = self.auditoria_port.contar_eventos(id_usuario, tipo_evento, fecha_desde, fecha_hasta)
        items = self.auditoria_port.listar_eventos(id_usuario, tipo_evento, fecha_desde, fecha_hasta, offset, tamano)

        # 5. Registrar evento de consulta
        try:
            self.sesiones_port.registrar_evento(
                tipo_evento=TIPO_CONSULTA_AUDITORIA,
                resultado=EnumEventoResultado.EXITOSO,
                id_usuario=usuario_actual.id_usuario,
                detalle={
                    "filtros": {
                        "id_usuario": id_usuario,
                        "tipo_evento": tipo_evento,
                        "fecha_desde": fecha_desde.isoformat() if fecha_desde else None,
                        "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else None,
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
            "items": items,
        }
