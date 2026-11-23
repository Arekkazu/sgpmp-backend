# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-78 F9 / RF-79 F2: consolidar y entregar |
# | 2026-11-08 | Arekkazu | INC-M05-265-G32: textos visibles sin códigos de requisito ni de módulo |
# | 2026-11-08 | Leandro | INC-M05-278-G39 RF-80: separar conciliación pendiente de campos ausentes en auditoría. |
# | 2026-11-14 | destroyerban | INC-M05-353-G37 RF-80: el rechazo de consolidar o corregir queda en la bitácora |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Caso de uso: consolidar la inversión de una instancia de ciclo cerrada (RF-78 Fase 9, RF-79 Fase 2).

Lo dispara el cierre del ciclo (RF-38, ``consolidar_sin_commit`` dentro de la
transacción del cierre) o el Contador por el endpoint, siempre sobre un ciclo
ya CERRADO (R2; un ciclo activo → 409, E2).

- Monto = Σ ``costo_registro`` del ledger (RF-78 R7).
- Potencialmente incompleto si el monto no cuadra con el acumulado, con lo
  provisto incrementalmente, o si quedan eventos sin entregar a M06 (R11, E6,
  E7 f); en ese caso se avisa al Contador (E3).
- Se persiste el reporte (append-only, hash por trigger), el acumulado queda
  CONSOLIDADO, se registran ``CICLO_CONSOLIDADO`` y ``REPORTE_COSTOS_GENERADO``
  (RF-80) y el reporte va al outbox hacia M06 (Fase 2 h).

Si ya existía una versión, esta produce la siguiente (``version_reporte = N+1``).

Un intento rechazado (ciclo activo, inexistente o sin suministros) o fallido se
revierte y deja su evento en la bitácora en una transacción aparte (RF-80 CA-1),
con el tipo de la operación y resultado ``RECHAZADO``/``FALLIDO``; lo mismo hace
la corrección (``REPORTE_COSTOS_GENERADO``). El cierre del ciclo (RF-38) llama a
``consolidar_sin_commit`` y conserva su propio manejo de errores.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, ConflictError, NotFoundError
from src.supplies.domain.entities.evento_provision_m06 import EventoProvisionM06
from src.supplies.domain.entities.provision_nic41 import ProvisionNic41
from src.supplies.domain.repositories.acumulado_ciclo_repository import AcumuladoCicloRepository
from src.supplies.domain.repositories.auditoria_suministro_port import (
    AuditoriaSuministroPort,
    EventoAuditoriaSuministro,
)
from src.supplies.domain.repositories.ciclo_abierto_port import CicloAbiertoPort
from src.supplies.domain.repositories.notificacion_suministros_port import NotificacionSuministrosPort
from src.supplies.domain.repositories.outbox_provision_m06_repository import OutboxProvisionM06Repository
from src.supplies.domain.repositories.provision_nic41_repository import ProvisionNic41Repository
from src.supplies.domain.repositories.registro_suministro_repository import RegistroSuministroRepository
from src.supplies.domain.services.consolidador_nic41 import construir_consolidado
from src.supplies.domain.value_objects.eventos_auditoria_suministro_enums import (
    ResultadoAuditoriaSuministro,
    TipoEventoAuditoriaSuministro,
)

# Recurso provision_nic41 (56), acción E: el Contador recibe el aviso de reporte incompleto.
_RECURSO_PROVISION, _ACCION_EJECUTAR = 56, 5
_LOGGER = logging.getLogger(__name__)
# Lo que lee el auditor en la bitácora: en palabras, sin el código del error.
_MOTIVOS_RECHAZO = {
    "CICLO_ACTIVO": "el ciclo productivo sigue activo; el reporte consolidado solo se genera tras su cierre.",
    "CICLO_NO_ENCONTRADO": "la instancia de ciclo productivo no existe.",
    "SIN_INFORMACION_ACUMULADA": "el ciclo no tiene suministros acumulados para consolidar.",
    "PROVISION_NO_ENCONTRADA": "el reporte de provisión a corregir no existe.",
    "MOTIVO_CORRECCION_INSUFICIENTE": "el motivo de la corrección es demasiado corto.",
    "MOTIVO_CORRECCION_MUY_LARGO": "el motivo de la corrección supera la longitud permitida.",
}
_OPERACION = {
    TipoEventoAuditoriaSuministro.CICLO_CONSOLIDADO: "Consolidación del ciclo",
    TipoEventoAuditoriaSuministro.REPORTE_COSTOS_GENERADO: "Corrección del reporte consolidado",
}


class ConsolidarCicloUseCase:
    """Consolida la provisión NIC 41 de suministros de un ciclo."""
    def __init__(
        self,
        db: Session,
        ciclo_port: CicloAbiertoPort,
        acumulado_repo: AcumuladoCicloRepository,
        registro_repo: RegistroSuministroRepository,
        provision_repo: ProvisionNic41Repository,
        auditoria_port: AuditoriaSuministroPort,
        outbox_repo: OutboxProvisionM06Repository,
        notificador: Optional[NotificacionSuministrosPort] = None,
    ) -> None:
        self.db = db
        self.ciclo_port = ciclo_port
        self.acumulado_repo = acumulado_repo
        self.registro_repo = registro_repo
        self.provision_repo = provision_repo
        self.auditoria_port = auditoria_port
        self.outbox_repo = outbox_repo
        self.notificador = notificador

    def execute(self, id_gestion_fases: int, usuario_actual: UsuarioActual) -> ProvisionNic41:
        """Consolida la provisión del ciclo y la confirma."""
        try:
            provision = self.consolidar_sin_commit(id_gestion_fases, usuario_actual.id_usuario)
            self.db.commit()
        except AppError as exc:
            self.registrar_rechazo(
                TipoEventoAuditoriaSuministro.CICLO_CONSOLIDADO, usuario_actual.id_usuario, exc, id_gestion_fases
            )
            raise
        except Exception:
            self.db.rollback()
            raise
        self.avisar_si_incompleto(provision)
        return provision

    def registrar_rechazo(
        self,
        tipo: TipoEventoAuditoriaSuministro,
        id_usuario: int,
        error: AppError,
        id_gestion_fases: Optional[int],
    ) -> None:
        """Revierte el intento y confirma solo su evento en una transacción nueva (RF-80 CA-1).

        Patrón de RF-78 (``RegistrarSuministroDirectoUseCase._registrar_rechazo``):
        solo se enlaza la fase si existe; si la auditoría falla se conserva el
        error original y se deja un diagnóstico en el log.
        """
        try:
            self.db.rollback()
            fase = self.ciclo_port.obtener_por_id(id_gestion_fases) if id_gestion_fases is not None else None
            rechazado = error.status_code < 500
            motivo = (
                _MOTIVOS_RECHAZO.get(error.code, "la operación incumple una regla de negocio.")
                if rechazado else "ocurrió un error interno del sistema; no se guardó ningún cambio."
            )
            detalle = f"{_OPERACION[tipo]} {'rechazada' if rechazado else 'fallida'}: {motivo}"
            if id_gestion_fases is not None:
                detalle += f" Instancia de ciclo solicitada: {id_gestion_fases}."
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="provision_nic41",
                    tipo_operacion=tipo.value,
                    id_usuario=id_usuario,
                    resultado=(
                        ResultadoAuditoriaSuministro.RECHAZADO if rechazado else ResultadoAuditoriaSuministro.FALLIDO
                    ).value,
                    id_activo_biologico=fase.id_activo_biologico if fase else None,
                    id_ciclo_productivo=fase.id_ciclo_productivo if fase else None,
                    id_gestion_fases=fase.id_gestion_fases if fase else None,
                    detalle_causa=detalle,
                )
            )
            self.db.commit()
        except Exception:
            _LOGGER.error(
                "No se pudo auditar el rechazo de la provisión: usuario=%s fase=%s codigo=%s",
                id_usuario, id_gestion_fases, error.code,
            )
            try:
                self.db.rollback()
            except Exception:
                _LOGGER.error("No se pudo revertir la transacción de auditoría del rechazo de la provisión.")

    def consolidar_sin_commit(
        self, id_gestion_fases: int, id_usuario: int, *, exigir_registros: bool = True,
        motivo_correccion: Optional[str] = None,
    ) -> Optional[ProvisionNic41]:
        """Genera la versión siguiente del consolidado. Con ``motivo_correccion`` es una corrección (E4)."""
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
                    f"El ciclo {id_gestion_fases} está activo. El reporte consolidado solo está disponible "
                    "tras el cierre del ciclo productivo."
                ),
            )

        acumulado = self.acumulado_repo.obtener(id_gestion_fases)
        if acumulado is None:
            if not exigir_registros:
                return None  # ciclo cerrado sin suministros: no hay inversión que consolidar
            raise BusinessRuleError(
                code="SIN_INFORMACION_ACUMULADA",
                message=(
                    "No existen registros de suministros válidos para consolidar la inversión "
                    "acumulada de este ciclo."
                ),
            )
        registros = self.registro_repo.listar_por_gestion_fase(id_gestion_fases)
        resultado = construir_consolidado(
            registros,
            acumulado,
            suma_incremental=self.outbox_repo.sumar_incrementales(id_gestion_fases),
            eventos_sin_entregar=self.outbox_repo.contar_sin_entregar(id_gestion_fases),
        )

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
            motivo_correccion=motivo_correccion,
        )
        guardada = self.provision_repo.guardar(provision)
        if anterior is not None:
            self.provision_repo.marcar_superado(anterior.id_provision)
        self.acumulado_repo.marcar_consolidado(id_gestion_fases)
        tipos = [TipoEventoAuditoriaSuministro.REPORTE_COSTOS_GENERADO]
        if motivo_correccion is None:
            tipos.insert(0, TipoEventoAuditoriaSuministro.CICLO_CONSOLIDADO)
        for tipo in tipos:
            self.auditoria_port.registrar(
                EventoAuditoriaSuministro(
                    entidad_afectada="provision_nic41",
                    tipo_operacion=tipo.value,
                    id_usuario=id_usuario,
                    resultado=ResultadoAuditoriaSuministro.EXITOSO.value,
                    id_activo_biologico=guardada.id_activo_biologico,
                    id_ciclo_productivo=guardada.id_ciclo_productivo,
                    id_gestion_fases=id_gestion_fases,
                    costo_afectado=guardada.monto_provision,
                    detalle_causa=(
                        "Reporte pendiente de conciliación. " + " ".join(resultado.causas_incompletitud)
                        if resultado.causas_incompletitud else None
                    ),
                )
            )
        self.encolar_para_m06(guardada)
        return guardada

    def encolar_para_m06(self, provision: ProvisionNic41) -> None:
        """Encola la provisión consolidada para el módulo financiero."""
        self.outbox_repo.encolar(
            EventoProvisionM06.consolidado(
                contenido=provision.contenido_m06(),
                id_activo_biologico=provision.id_activo_biologico,
                id_gestion_fases=provision.id_gestion_fases,
                id_provision=provision.id_provision,
                ahora=datetime.now(timezone.utc),
            )
        )

    def avisar_si_incompleto(self, provision: Optional[ProvisionNic41]) -> None:
        """E3/E6: el Contador recibe el aviso cuando el reporte quedó potencialmente incompleto."""
        if provision is None or not provision.es_reporte_potencialmente_incompleto or self.notificador is None:
            return
        self.notificador.a_permiso(
            _RECURSO_PROVISION, _ACCION_EJECUTAR, "PROVISION_M06_PENDIENTE",
            f"El reporte consolidado NIC-41 {provision.id_provision} (ciclo {provision.id_gestion_fases}, "
            f"versión {provision.version_reporte}) quedó potencialmente incompleto: el monto del ledger no "
            "coincide con el acumulado o con lo provisto incrementalmente, o hay eventos sin entregar al módulo financiero. "
            "Revise el reporte y, si corresponde, solicite su corrección.",
            {"id_provision": provision.id_provision, "id_gestion_fases": provision.id_gestion_fases},
        )
