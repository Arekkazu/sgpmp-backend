"""Caso de uso: corregir un reporte consolidado NIC-41 (RF-79 E4, Restricción 3).

Genera una nueva versión (``version_reporte = N+1``, ``id_reporte_anterior``
apuntando a la versión corregida) recalculando el consolidado desde el estado
actual de ``registro_suministro``/``acumulado_ciclo`` — nunca modifica la fila
original. La inmutabilidad de cada versión (incluido su ``hash_integridad``,
calculado por el trigger de BD ``trg_provision_hash``) se preserva no
haciendo ningún ``UPDATE`` sobre versiones previas: "SUPERADO" es un estado
derivado (existe una versión posterior en la cadena), no una columna que se
muta — mutar ``estado`` recalcularía el hash de una fila que debe permanecer
como evidencia congelada de lo que se generó en su momento.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.services.consolidador_nic41 import construir_consolidado
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)
from src.supplies.domain.value_objects.motivo_correccion import MotivoCorreccion


class CorregirProvisionUseCase:
    """Genera una nueva versión de un reporte consolidado NIC-41 existente."""

    def __init__(
        self,
        db: Session,
        acumulado_repo: AcumuladoCicloRepository,
        registro_repo: RegistroSuministroRepository,
        provision_repo: ProvisionNic41Repository,
        auditoria_port: AuditoriaSuministroPort,
    ) -> None:
        self.db = db
        self.acumulado_repo = acumulado_repo
        self.registro_repo = registro_repo
        self.provision_repo = provision_repo
        self.auditoria_port = auditoria_port

    def execute(
        self, id_provision: int, motivo_correccion: str, usuario_actual: UsuarioActual
    ) -> ProvisionNic41:
        original = self.provision_repo.obtener(id_provision)
        if original is None:
            raise NotFoundError(
                code="PROVISION_NO_ENCONTRADA",
                message=f"El reporte de provisión {id_provision} no existe.",
            )
        motivo = MotivoCorreccion(motivo_correccion)

        acumulado = self.acumulado_repo.obtener(original.id_gestion_fases)
        registros = self.registro_repo.listar_por_gestion_fase(original.id_gestion_fases)
        resultado = construir_consolidado(registros, acumulado) if acumulado else None

        ultima = self.provision_repo.obtener_ultima_version(original.id_gestion_fases) or original
        provision = ProvisionNic41.crear(
            id_activo_biologico=original.id_activo_biologico,
            id_ciclo_productivo=original.id_ciclo_productivo,
            id_gestion_fases=original.id_gestion_fases,
            monto_provision=resultado.monto_provision if resultado else original.monto_provision,
            desglose_categoria=resultado.desglose_categoria if resultado else original.desglose_categoria,
            lista_registros=resultado.lista_registros if resultado else original.lista_registros,
            es_reporte_potencialmente_incompleto=(
                resultado.es_reporte_potencialmente_incompleto if resultado else True
            ),
            version_reporte=ultima.version_reporte + 1,
            id_reporte_anterior=ultima.id_provision,
            motivo_correccion=motivo.valor,
        )
        try:
            guardada = self.provision_repo.guardar(provision)
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="provision_nic41",
                    tipo_operacion=TipoEventoAuditoriaSuministro.REPORTE_COSTOS_GENERADO.value,
                    id_usuario=usuario_actual.id_usuario,
                    resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                    id_activo_biologico=guardada.id_activo_biologico,
                    id_ciclo_productivo=guardada.id_ciclo_productivo,
                    id_gestion_fases=guardada.id_gestion_fases,
                    costo_afectado=guardada.monto_provision,
                    registro_incompleto=guardada.es_reporte_potencialmente_incompleto,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return guardada
