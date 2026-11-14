# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-90 v2.0: costo manual con naturaleza, origen, factura y reparto |
# | 2026-11-05 | Arekkazu | M06: mensajes sin códigos de módulo ni valores de enum |
# | 2026-11-08 | Arekkazu | INC-M06-329-G85 RF-90: reparto sin participación positiva responde 422 antes de tocar el período |
"""Caso de uso RF-90: registro manual de un costo (Contador o Administrador).

Eje 1 (naturaleza, NIC 41) decide el tratamiento; eje 2 (origen) decide el vehículo:
``COMPRA_PROVEEDOR``/``SERVICIO_TERCERO`` viajan como factura de compra (02) por M07 y no generan
línea; ``MANO_OBRA_PROPIA`` genera línea de asiento; ``CONSUMO_INVENTARIO`` está reservado a M05.
Un costo de VENTA no genera asiento ni documento (CA-10). Una INVERSIÓN se lleva a gasto salvo en
activos valorados por costo, donde el Contador puede capitalizarla (D-4)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.application.services.contabilizador import Contabilizador
from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria, LineaAsiento
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.costo_repository import CostoRepository
from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.financial_valuation.domain.services.nic41 import repartir
from src.financial_valuation.domain.value_objects.nic41 import (
    ETIQUETA_NATURALEZA,
    ETIQUETA_SUBTIPO,
    NATURALEZA_POR_SUBTIPO,
    ORIGENES_CON_PROVEEDOR,
    MetodoReparto,
    NaturalezaCosto,
    OrigenCosto,
    Sentido,
    Severidad,
    SubtipoCosto,
    TipoEvidencia,
    TipoHecho,
    VehiculoContable,
)
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from src.shared.fechas import hoy_usuario

AVISO_FUENTE_UNICA = ("Esta factura llegará a la contabilidad por la exportación contable de SIGAB: no la registre manualmente en "
                      "SIGCON. Las compras de insumos para inventario general se registran directamente en SIGCON.")


@dataclass
class SolicitudCosto:
    subtipo_costo: str
    origen_costo: str
    monto_costo: Decimal
    fecha_costo: date
    id_activo_biologico: Optional[int] = None
    activos_reparto: list[int] = field(default_factory=list)
    metodo_reparto: str = MetodoReparto.POR_CABEZAS.value
    naturaleza_costo: Optional[str] = None
    justificacion: Optional[str] = None
    tercero_nit: Optional[str] = None
    tercero_dv: Optional[str] = None
    tercero_razon_social: Optional[str] = None
    factura_prefijo: Optional[str] = None
    factura_numero: Optional[str] = None
    fecha_factura: Optional[date] = None
    fecha_vencimiento_factura: Optional[date] = None
    cuenta_debito_manual: Optional[str] = None
    confirmar_capitalizacion: bool = False


class RegistrarCostoUseCase:
    def __init__(self, db: Session, costos: CostoRepository, activos: ActivoFinancieroPort,
                 valoraciones: ValoracionRepository, contabilizador: Contabilizador) -> None:
        self.db = db
        self.costos = costos
        self.activos = activos
        self.valoraciones = valoraciones
        self.contabilizador = contabilizador

    def execute(self, s: SolicitudCosto, id_usuario: int) -> dict:
        if s.origen_costo == OrigenCosto.CONSUMO_INVENTARIO.value:  # FA-12
            raise BusinessRuleError(code="ORIGEN_RESERVADO_M05",
                                    message="El origen consumo de inventario lo registra automáticamente Suministros.")
        if s.fecha_costo > hoy_usuario():
            raise ValidationError(code="FECHA_COSTO_FUTURA", message="La fecha del costo no puede ser futura.", field="fecha_costo")
        naturaleza = self._naturaleza(s)
        justificacion = (s.justificacion or "").strip()
        requiere = (s.subtipo_costo == SubtipoCosto.OTRO.value or naturaleza in (NaturalezaCosto.INVERSION.value,
                    NaturalezaCosto.VENTA.value) or s.cuenta_debito_manual)
        if requiere and len(justificacion) < 10:  # FA-10
            raise BusinessRuleError(code="JUSTIFICACION_OBLIGATORIA", field="justificacion",
                                    message="Este costo requiere una justificación (mínimo 10 caracteres).")
        con_proveedor = s.origen_costo in {o.value for o in ORIGENES_CON_PROVEEDOR}
        if con_proveedor:
            self._validar_factura(s)
        activos = self._activos(s)
        montos = self._repartir(s, activos)  # antes del período: un reparto inválido no deja efectos
        periodo = self.contabilizador.periodo_para(activos[0].numero_id_tributaria, s.fecha_costo, id_usuario)
        if not periodo.contiene(s.fecha_costo):  # FA-4
            raise BusinessRuleError(code="PERIODO_CONTABLE_CERRADO", field="fecha_costo", message=(
                "La fecha del costo pertenece a un período cerrado. Regístrelo como ajuste en el período abierto."))
        politica, sentido = self._politica(naturaleza, activos, s)
        vehiculo = (VehiculoContable.NINGUNO if naturaleza == NaturalezaCosto.VENTA.value or naturaleza is None
                    else VehiculoContable.FACTURA_COMPRA if con_proveedor else VehiculoContable.ASIENTO_NIC41).value
        if naturaleza is None and s.origen_costo == OrigenCosto.MANO_OBRA_PROPIA.value:
            vehiculo = VehiculoContable.ASIENTO_NIC41.value  # la línea se crea al clasificar
        cuenta_factura = None
        if vehiculo == VehiculoContable.FACTURA_COMPRA.value and not s.cuenta_debito_manual:
            cuenta_factura = self.contabilizador.config.resolver_cuenta(
                TipoHecho.CONSUMO_INSUMO.value, Sentido.UNICO.value, activos[0].id_especie, s.subtipo_costo)
            if cuenta_factura is None:  # FA-7
                raise BusinessRuleError(code="CUENTA_NO_CONFIGURADA", message=(
                    f"La matriz contable no tiene cuenta de gasto para {ETIQUETA_SUBTIPO.get(s.subtipo_costo, s.subtipo_costo)}. "
                    "Complétela en Configuración contable."))
        grupo = uuid.uuid4() if len(activos) > 1 else None
        registros = []
        try:
            for activo in activos:
                registros.append(self._registrar(activo, montos[activo.id_activo_biologico], s, naturaleza, politica,
                                                 sentido, vehiculo, cuenta_factura, periodo, grupo, justificacion, id_usuario))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"registros": registros, "id_grupo_reparto": grupo,
                "aviso": AVISO_FUENTE_UNICA if con_proveedor else None}

    def _naturaleza(self, s: SolicitudCosto) -> Optional[str]:
        if s.subtipo_costo == SubtipoCosto.OTRO.value:
            return s.naturaleza_costo  # sin naturaleza → PENDIENTE_CLASIFICACION (FA-3)
        propia = NATURALEZA_POR_SUBTIPO[SubtipoCosto(s.subtipo_costo)].value
        if s.naturaleza_costo and s.naturaleza_costo != propia:  # FA-2: MANTENIMIENTO no se reclasifica
            raise BusinessRuleError(code="RECLASIFICACION_NO_PERMITIDA", message=(
                f"Un costo de {ETIQUETA_SUBTIPO.get(s.subtipo_costo, s.subtipo_costo)} es de {ETIQUETA_NATURALEZA[propia]} y no puede "
                f"registrarse como {ETIQUETA_NATURALEZA.get(s.naturaleza_costo, s.naturaleza_costo)}."))
        return propia

    def _validar_factura(self, s: SolicitudCosto) -> None:
        faltantes = [c for c in ("tercero_nit", "tercero_dv", "tercero_razon_social", "factura_numero", "fecha_factura",
                                 "fecha_vencimiento_factura") if not getattr(s, c)]
        if faltantes:  # FA-5
            raise BusinessRuleError(code="DATOS_PROVEEDOR_INCOMPLETOS", field=faltantes[0],
                                    message=f"Faltan datos del proveedor o de la factura: {', '.join(faltantes)}.")
        if s.fecha_vencimiento_factura < s.fecha_factura:
            raise ValidationError(code="FECHA_VENCIMIENTO_FACTURA_INVALIDA", field="fecha_vencimiento_factura",
                                  message="El vencimiento de la factura no puede ser anterior a su fecha.")
        existente = self.costos.factura_registrada(s.tercero_nit, s.factura_prefijo, s.factura_numero)
        if existente is not None:  # FA-6
            raise ConflictError(code="FACTURA_DUPLICADA", message=(
                f"La factura {s.factura_prefijo or ''}{s.factura_numero} del NIT {s.tercero_nit} ya está registrada como costo."))

    def _activos(self, s: SolicitudCosto):
        ids = s.activos_reparto or ([s.id_activo_biologico] if s.id_activo_biologico else [])
        if not ids:  # FA-1
            raise BusinessRuleError(code="COSTO_SIN_ACTIVO", message="Indique el activo o los activos del costo.")
        if len(set(ids)) != len(ids):  # FA-11
            raise BusinessRuleError(code="REPARTO_INVALIDO", message="La lista de reparto tiene activos repetidos.")
        activos = []
        for id_activo in ids:
            activo = self.activos.obtener(id_activo)
            if activo is None:
                raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message=f"El activo {id_activo} no existe.")
            if not activo.es_valorable or self.valoraciones.reconocimiento_confirmado(id_activo) is None:
                raise BusinessRuleError(code="ACTIVO_NO_DISPONIBLE", message=(
                    f"El activo {activo.identificador} no está reconocido o no está activo."))
            activos.append(activo)
        if len({a.numero_id_tributaria for a in activos}) > 1:
            raise BusinessRuleError(code="REPARTO_INVALIDO", message="Todos los activos del reparto deben ser del mismo titular.")
        return activos

    def _politica(self, naturaleza, activos, s) -> tuple[Optional[str], str]:
        if naturaleza == NaturalezaCosto.VENTA.value or naturaleza is None:
            return None, Sentido.UNICO.value
        if naturaleza == NaturalezaCosto.INVERSION.value and s.confirmar_capitalizacion:
            if any(self.valoraciones.valoracion_costo_activa(a.id_activo_biologico) is None for a in activos):
                raise BusinessRuleError(code="CAPITALIZACION_NO_PERMITIDA", message=(
                    "Solo se capitalizan inversiones en activos valorados por costo: en un activo a valor razonable la "
                    "inversión es gasto del período (la medición posterior ya refleja su efecto)."))
            return "CAPITALIZAR", Sentido.CAPITALIZACION.value
        return "GASTO", Sentido.UNICO.value

    @staticmethod
    def _repartir(s: SolicitudCosto, activos) -> dict[int, Decimal]:
        if len(activos) == 1:
            return {activos[0].id_activo_biologico: Decimal(s.monto_costo)}
        biomasa = s.metodo_reparto == MetodoReparto.POR_BIOMASA.value and all(a.peso_kg for a in activos)
        pesos = {a.id_activo_biologico: (Decimal(a.peso_kg) * a.cabezas if biomasa else Decimal(a.cabezas)) for a in activos}
        if sum(pesos.values()) <= 0:  # FA-11: sin cabezas ni biomasa no hay proporción que aplicar
            raise BusinessRuleError(code="REPARTO_INVALIDO", field="activos_reparto", message=(
                "Los activos del reparto no tienen cabezas ni biomasa registradas: no es posible repartir el costo "
                "en proporción. Revise la población o el último pesaje de los activos."))
        return repartir(Decimal(s.monto_costo), pesos)

    def _registrar(self, activo, monto, s, naturaleza, politica, sentido, vehiculo, cuenta_factura, periodo, grupo,
                   justificacion, id_usuario) -> dict:
        datos = {k: getattr(s, k) for k in ("tercero_nit", "tercero_dv", "tercero_razon_social", "factura_prefijo",
                                            "factura_numero", "fecha_factura", "fecha_vencimiento_factura")}
        id_costo = self.costos.agregar({
            **datos, "naturaleza_costo": naturaleza, "subtipo_costo": s.subtipo_costo,
            "id_activo_biologico": activo.id_activo_biologico, "monto_costo": monto,
            "politica_capitalizacion": politica, "estado": "REGISTRADO" if naturaleza else "PENDIENTE_CLASIFICACION",
            "justificacion": justificacion or None, "id_periodo_contable": periodo.id_periodo_contable,
            "id_usuario": id_usuario, "origen_costo": s.origen_costo, "vehiculo_contable": vehiculo,
            "fecha_costo": s.fecha_costo, "id_grupo_reparto": grupo,
            "metodo_reparto": s.metodo_reparto if grupo else None,
            "cuenta_debito": s.cuenta_debito_manual or (cuenta_factura.cuenta_debito if cuenta_factura else None),
            "es_cuenta_manual": bool(s.cuenta_debito_manual),
        })
        linea = None
        if naturaleza and vehiculo == VehiculoContable.ASIENTO_NIC41.value:
            linea = self.contabilizador.asentar(LineaAsiento(
                tipo_hecho=TipoHecho.MANO_OBRA_PROPIA.value, sentido=sentido, valor=Decimal(monto).quantize(Decimal("0.01")),
                fecha_hecho=s.fecha_costo, id_periodo_contable=periodo.id_periodo_contable,
                id_activo_biologico=activo.id_activo_biologico, id_especie=activo.id_especie, id_finca=activo.id_finca,
                numero_id_tributaria=activo.numero_id_tributaria, tabla_origen="registros_costos", id_origen=id_costo,
                tipo_evidencia=TipoEvidencia.REGISTRO_MANUAL.value, subtipo_costo=s.subtipo_costo,
                justificacion=justificacion or None, id_usuario=id_usuario,
            ), id_usuario)
        if politica == "CAPITALIZAR":
            costo = self.valoraciones.valoracion_costo_activa(activo.id_activo_biologico)
            costo.costos_adquisicion += monto
            costo.valor_contable_por_costo += monto
            self.valoraciones.actualizar_valoracion_costo(costo)
        self.contabilizador.auditar(EventoAuditoria(
            tipo_evento="COSTO_REGISTRADO", severidad=Severidad.INFO.value, id_usuario=id_usuario,
            payload={"naturaleza": naturaleza, "subtipo": s.subtipo_costo, "origen": s.origen_costo, "vehiculo": vehiculo,
                     "politica": politica, "factura": f"{s.factura_prefijo or ''}{s.factura_numero or ''}" or None,
                     "tercero_nit": s.tercero_nit, "id_grupo_reparto": str(grupo) if grupo else None,
                     "cuenta_manual": s.cuenta_debito_manual},
            id_activo_biologico=activo.id_activo_biologico, id_periodo_contable=periodo.id_periodo_contable,
            id_referencia=id_costo, monto_afectado=monto,
        ))
        return {"id_registro_costo": id_costo, "id_activo_biologico": activo.id_activo_biologico, "monto_costo": monto,
                "naturaleza_costo": naturaleza, "vehiculo_contable": vehiculo,
                "estado": "REGISTRADO" if naturaleza else "PENDIENTE_CLASIFICACION",
                "id_linea_asiento": linea.id_linea_asiento_nic41 if linea else None}
