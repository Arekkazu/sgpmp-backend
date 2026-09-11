"""Caso de uso: consolidar el reporte NIC-41 al cierre de una instancia de ciclo (RF-79).

RF-41 (M02) no tiene ningún hook implementado en la app que notifique el
cierre de un ciclo a M05 (Gap 9 de ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``).
Este caso de uso asume el rol de "disparador" de la consolidación: verifica
directamente en ``gestiones_fases`` que la instancia de ciclo esté cerrada
(``es_activa=False`` y ``fecha_finalizacion`` presente) antes de generar el
reporte definitivo.

Comparte la cadena de versiones con :class:`GenerarProvisionManualUseCase`
(``application/use_cases/provision_nic41/generar_provision_manual_use_case.py``):
si ya existe una versión previa (generada aquí o de forma manual antes del
cierre), esta consolidación produce la siguiente versión (``version_reporte
= N+1``, ``id_reporte_anterior`` apuntando a la anterior) en vez de fallar —
no hay forma de distinguir en el esquema de BD un snapshot manual de uno
disparado por cierre, así que ambos caminos alimentan la misma cadena
auditable en vez de bloquearse entre sí.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.services.consolidador_nic41 import construir_consolidado
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)


class ConsolidarCicloUseCase:
    """Genera el reporte consolidado NIC-41 (versión 1) al cierre de una instancia de ciclo."""

    def __init__(
        self,
        db: Session,
        ciclo_port: CicloAbiertoPort,
        acumulado_repo: AcumuladoCicloRepository,
        registro_repo: RegistroSuministroRepository,
        provision_repo: ProvisionNic41Repository,
        auditoria_port: AuditoriaSuministroPort,
    ) -> None:
        self.db = db
        self.ciclo_port = ciclo_port
        self.acumulado_repo = acumulado_repo
        self.registro_repo = registro_repo
        self.provision_repo = provision_repo
        self.auditoria_port = auditoria_port

    def execute(self, id_gestion_fases: int, usuario_actual: UsuarioActual) -> ProvisionNic41:
        fase = self.ciclo_port.obtener_por_id(id_gestion_fases)
        if fase is None:
            raise NotFoundError(
                code="CICLO_NO_ENCONTRADO",
                message=f"La instancia de ciclo productivo {id_gestion_fases} no existe.",
            )
        if fase.es_activa or fase.fecha_finalizacion is None:
            raise ConflictError(
                code="CICLO_ACTIVO",
                message=(
                    f"El ciclo {id_gestion_fases} está activo. El reporte consolidado solo está "
                    "disponible tras el cierre del ciclo."
                ),
            )

        acumulado = self.acumulado_repo.obtener(id_gestion_fases)
        if acumulado is None:
            raise BusinessRuleError(
                code="SIN_INFORMACION_ACUMULADA",
                message=(
                    "No existen registros de suministros válidos para consolidar la inversión "
                    "acumulada de este ciclo."
                ),
            )
        registros = self.registro_repo.listar_por_gestion_fase(id_gestion_fases)
        resultado = construir_consolidado(registros, acumulado)

        anterior = self.provision_repo.obtener_ultima_version(id_gestion_fases)
        provision = ProvisionNic41.crear(
            id_activo_biologico=acumulado.id_activo_biologico,
            id_ciclo_productivo=acumulado.id_ciclo_productivo,
            id_gestion_fases=id_gestion_fases,
            monto_provision=resultado.monto_provision,
            desglose_categoria=resultado.desglose_categoria,
            lista_registros=resultado.lista_registros,
            es_reporte_potencialmente_incompleto=resultado.es_reporte_potencialmente_incompleto,
            version_reporte=(anterior.version_reporte + 1) if anterior else 1,
            id_reporte_anterior=anterior.id_provision if anterior else None,
        )
        try:
            guardada = self.provision_repo.guardar(provision)
            self.acumulado_repo.marcar_consolidado(id_gestion_fases)
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="provision_nic41",
                    tipo_operacion=TipoEventoAuditoriaSuministro.CICLO_CONSOLIDADO.value,
                    id_usuario=usuario_actual.id_usuario,
                    resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                    id_activo_biologico=guardada.id_activo_biologico,
                    id_ciclo_productivo=guardada.id_ciclo_productivo,
                    id_gestion_fases=id_gestion_fases,
                    costo_afectado=guardada.monto_provision,
                    registro_incompleto=guardada.es_reporte_potencialmente_incompleto,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return guardada
