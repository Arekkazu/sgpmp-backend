# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82 R2/paso 10: reversión auditada del reconocimiento inicial |
"""Caso de uso RF-82 paso 10: asiento espejo y el activo vuelve a la bandeja de propuestas."""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.value_objects.nic41 import Severidad
from src.shared.errors import ConflictError, NotFoundError, ValidationError
from src.shared.fechas import hoy_usuario


class RevertirReconocimientoUseCase:
    def __init__(self, db: Session, activos: ActivoFinancieroPort, valoraciones: ValoracionRepository,
                 contabilizador: Contabilizador) -> None:
        self.db = db
        self.activos = activos
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador

    def execute(self, id_activo_biologico: int, motivo: str, id_usuario: int) -> dict:
        if len((motivo or "").strip()) < 20:  # R2 c / CA-15
            raise ValidationError(code="MOTIVO_REVERSION_INSUFICIENTE",
                                  message="El motivo de la reversión debe tener al menos 20 caracteres.", field="motivo")
        reconocimiento = self.valoraciones.reconocimiento_confirmado(id_activo_biologico)
        activo = self.activos.obtener(id_activo_biologico)
        if reconocimiento is None or activo is None:
            raise NotFoundError(code="RECONOCIMIENTO_NO_ENCONTRADO", message="El activo no tiene un reconocimiento vigente.")
        dependientes = self.valoraciones.dependientes_reconocimiento(reconocimiento)
        periodo_original = self.contabilizador.periodos.obtener(reconocimiento.id_periodo_contable)
        if periodo_original is not None and not periodo_original.esta_abierto:
            dependientes.append({"tipo": "CIERRE_PERIODO", "id": periodo_original.id_periodo_contable,
                                 "fecha": periodo_original.fecha_fin})
        if dependientes:  # R2 b / FA-6
            self._auditar_bloqueo(reconocimiento, dependientes, id_usuario)
            detalle = "; ".join(f"{d['tipo']} #{d['id']} ({d['fecha']:%Y-%m-%d})" for d in dependientes[:10])
            raise ConflictError(code="REVERSION_BLOQUEADA", message=(
                f"No es posible revertir el reconocimiento inicial del activo {activo.identificador}. Existen registros "
                f"contables dependientes: {detalle}. Para corregir la valoración use un ajuste en el período vigente."))
        try:
            hoy = hoy_usuario()
            periodo = self.contabilizador.periodo_para(activo.numero_id_tributaria, hoy, id_usuario)
            originales = self.contabilizador.asientos.lineas_de_origen("reconocimientos_iniciales",
                                                                      reconocimiento.id_reconocimiento_inicial)
            id_revision = self.valoraciones.revertir_reconocimiento(
                reconocimiento.id_reconocimiento_inicial, motivo.strip(), id_usuario,
                reconocimiento.valor_razonable_neto_inicial,
                reconocimiento.cuenta_credito or "SIN_CUENTA", reconocimiento.cuenta_debito or "SIN_CUENTA")
            espejos = self.contabilizador.revertir_lineas(originales, periodo, hoy, "revisiones_reconocimiento",
                                                          id_revision, motivo.strip(), id_usuario)
            costo = self.valoraciones.valoracion_costo_activa(id_activo_biologico)
            if costo is not None:
                costo.es_activa = False
                self.valoraciones.actualizar_valoracion_costo(costo)
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="RECONOCIMIENTO_REVERTIDO", severidad=Severidad.WARNING.value,
                payload={"motivo_reversion": motivo.strip(), "id_reconocimiento_revertido": reconocimiento.id_reconocimiento_inicial,
                         "lineas_espejo": [ln.id_linea_asiento_nic41 for ln in espejos]},
                id_usuario=id_usuario, id_activo_biologico=id_activo_biologico,
                id_periodo_contable=periodo.id_periodo_contable, id_referencia=id_revision,
                monto_afectado=reconocimiento.valor_razonable_neto_inicial,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"id_revision_reconocimiento": id_revision,
                "id_reconocimiento_revertido": reconocimiento.id_reconocimiento_inicial,
                "lineas_espejo": [ln.id_linea_asiento_nic41 for ln in espejos]}

    def _auditar_bloqueo(self, reconocimiento, dependientes, id_usuario) -> None:
        try:
            self.contabilizador.auditar(EventoAuditoria(
                tipo_evento="REVERSION_BLOQUEADA", severidad=Severidad.WARNING.value,
                payload={"dependientes": dependientes[:50]}, id_usuario=id_usuario,
                id_activo_biologico=reconocimiento.id_activo_biologico,
                id_referencia=reconocimiento.id_reconocimiento_inicial,
            ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
