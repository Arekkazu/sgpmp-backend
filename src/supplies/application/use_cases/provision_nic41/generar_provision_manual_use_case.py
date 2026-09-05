"""Caso de uso: generar una provisión CONSOLIDADO manual ad-hoc (RF-79).

RF-79: "M06 puede solicitar además una provisión CONSOLIDADO manual para
auditorías o recálculos" — a diferencia de :class:`ConsolidarCicloUseCase`, no
exige que la instancia de ciclo esté cerrada, y por eso **siempre** marca
``es_reporte_potencialmente_incompleto=True`` (un ciclo aún activo puede
recibir más suministros después de este snapshot). Comparte la misma cadena
de versiones que la consolidación por cierre (ver docstring de
``consolidar_ciclo_use_case.py``).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError
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


class GenerarProvisionManualUseCase:
    """Genera un reporte consolidado ad-hoc, sin exigir cierre de ciclo."""

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

    def execute(self, id_gestion_fases: int, usuario_actual: UsuarioActual) -> ProvisionNic41:
        acumulado = self.acumulado_repo.obtener(id_gestion_fases)
        if acumulado is None:
            raise BusinessRuleError(
                code="SIN_INFORMACION_ACUMULADA",
                message=(
                    "No existen registros de suministros válidos para generar la provisión "
                    "manual de este ciclo."
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
            es_reporte_potencialmente_incompleto=True,
            version_reporte=(anterior.version_reporte + 1) if anterior else 1,
            id_reporte_anterior=anterior.id_provision if anterior else None,
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
                    id_gestion_fases=id_gestion_fases,
                    costo_afectado=guardada.monto_provision,
                    registro_incompleto=True,
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return guardada
