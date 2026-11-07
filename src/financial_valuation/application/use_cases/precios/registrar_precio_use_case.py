# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-89: registro append-only de precios de mercado (NIC 41 ¶17) |
"""Caso de uso RF-89 pasos 3-8. El historial es inmutable: un precio erróneo se corrige con uno nuevo
que referencia al anterior (FA-6). Una desviación mayor al umbral exige confirmación (FA-7). Un
precio con vigencia futura queda PROGRAMADO (FA-9)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria
from src.financial_valuation.domain.repositories.activo_financiero_port import ActivoFinancieroPort
from src.financial_valuation.domain.repositories.auditoria_financiera_repository import AuditoriaFinancieraRepository
from src.financial_valuation.domain.repositories.configuracion_contable_repository import ConfiguracionContableRepository
from src.financial_valuation.domain.repositories.notificacion_financiera_port import NotificacionFinancieraPort
from src.financial_valuation.domain.repositories.precio_repository import PrecioRepository
from src.financial_valuation.domain.services.precios import Precio, desviacion_pct, precio_vigente
from src.financial_valuation.domain.value_objects.nic41 import CategoriaPrecio, FuentePrecio
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from src.shared.fechas import hoy_usuario

UNIDAD_POR_CATEGORIA = {CategoriaPrecio.PESO_KG.value: "kg", CategoriaPrecio.POR_CABEZA.value: "cabeza"}


@dataclass
class SolicitudPrecio:
    id_especie: int
    categoria: str
    precio_unitario: Decimal
    fecha_vigencia: date
    fuente: str
    evidencia_documental: str
    fecha_vencimiento: Optional[date] = None
    id_metrica_produccion: Optional[int] = None
    justificacion_estimacion: Optional[str] = None
    id_precio_corregido: Optional[int] = None
    confirmar_desviacion: bool = False


class RegistrarPrecioUseCase:
    def __init__(self, db: Session, precios: PrecioRepository, config: ConfiguracionContableRepository,
                 auditoria: AuditoriaFinancieraRepository, catalogo: ActivoFinancieroPort, notificador: NotificacionFinancieraPort) -> None:
        self.db = db
        self.precios = precios
        self.config = config
        self.auditoria = auditoria
        self.catalogo = catalogo
        self.notificador = notificador

    def execute(self, s: SolicitudPrecio, id_usuario: int) -> dict:
        hoy = hoy_usuario()
        unidad = self._validar(s, hoy)
        lista = self.precios.de_especie(s.id_especie, s.categoria, s.id_metrica_produccion)
        anterior = precio_vigente([p for p in lista if p.fuente == s.fuente], hoy)
        desviacion = desviacion_pct(s.precio_unitario, anterior.precio_unitario) if anterior else None
        umbral = self.config.obtener().pct_umbral_desviacion_precio
        if desviacion is not None and desviacion > umbral and not s.confirmar_desviacion:  # FA-7
            raise ConflictError(code="DESVIACION_PRECIO_REQUIERE_CONFIRMACION", message=(
                f"El precio difiere {desviacion:.1f}% del vigente ({anterior.precio_unitario:,.2f} por {unidad}), más que el "
                f"umbral de {umbral}%. Confirme que es correcto para guardarlo."))
        estado = "PROGRAMADO" if s.fecha_vigencia > hoy else "ACTIVO"
        try:
            precio = self.precios.agregar(Precio(
                id_precio_mercado=0, id_especie=s.id_especie, categoria=s.categoria, precio_unitario=s.precio_unitario,
                unidad_medida=unidad, fuente=s.fuente, fecha_vigencia=s.fecha_vigencia,
                fecha_vencimiento=s.fecha_vencimiento, id_metrica_produccion=s.id_metrica_produccion,
                evidencia=s.evidencia_documental.strip(), justificacion=(s.justificacion_estimacion or "").strip() or None,
                id_precio_corregido=s.id_precio_corregido,
            ), None, "MANUAL", id_usuario, estado)
            self.auditoria.registrar(EventoAuditoria(
                tipo_evento="PRECIO_REGISTRADO", severidad="INFO", id_usuario=id_usuario,
                payload={"id_especie": s.id_especie, "categoria": s.categoria, "precio_unitario": str(s.precio_unitario),
                         "fuente": s.fuente, "estado": estado, "fecha_vigencia": s.fecha_vigencia,
                         "desviacion_pct": str(desviacion) if desviacion is not None else None,
                         "desviacion_confirmada": s.confirmar_desviacion, "id_precio_corregido": s.id_precio_corregido},
                id_referencia=precio.id_precio_mercado, monto_afectado=s.precio_unitario,
            ))
            if anterior is not None and s.fecha_vigencia >= anterior.fecha_vigencia:  # RF-94 CA-14
                self.auditoria.registrar(EventoAuditoria(
                    tipo_evento="PRECIO_MARCADO_REEMPLAZADO", severidad="INFO", id_usuario=id_usuario,
                    payload={"id_precio_anterior": anterior.id_precio_mercado, "id_precio_nuevo": precio.id_precio_mercado},
                    id_referencia=precio.id_precio_mercado,
                ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        if estado == "ACTIVO" and s.categoria != CategoriaPrecio.PRODUCTO.value:  # RF-88 CA-12 / ¶30
            self.notificador.a_contadores("ALERTA_FINANCIERA_NIC41", (
                "Hay un nuevo precio de mercado vigente. Si tiene activos de esta especie valorados por costo, la NIC 41 "
                "exige pasarlos a valor razonable (Valoración por costo)."), {"id_precio_mercado": precio.id_precio_mercado})
        return {"id_precio_mercado": precio.id_precio_mercado, "estado": estado, "unidad_medida": unidad,
                "desviacion_pct": desviacion, "fecha_vigencia": s.fecha_vigencia}

    def _validar(self, s: SolicitudPrecio, hoy: date) -> str:
        especie = self.catalogo.especie(s.id_especie)
        if especie is None or not especie["es_activo"]:
            raise NotFoundError(code="ESPECIE_NO_ENCONTRADA", message="La especie no existe o está inactiva.")
        if s.precio_unitario <= 0:  # FA-1
            raise ValidationError(code="PRECIO_NO_POSITIVO", field="precio_unitario", message=(
                "El precio debe ser mayor a cero. Si el activo no tiene valor de mercado, aplique la valoración por costo."))
        if (hoy - s.fecha_vigencia).days > 365:
            raise ValidationError(code="FECHA_VIGENCIA_FUERA_DE_RANGO", field="fecha_vigencia",
                                  message="La fecha de vigencia no puede ser anterior en más de 365 días a hoy.")
        if s.fecha_vencimiento is not None and s.fecha_vencimiento <= s.fecha_vigencia:
            raise ValidationError(code="FECHA_VENCIMIENTO_INVALIDA", field="fecha_vencimiento",
                                  message="El vencimiento debe ser posterior a la fecha de vigencia.")
        if not (s.evidencia_documental or "").strip():
            raise ValidationError(code="EVIDENCIA_OBLIGATORIA", field="evidencia_documental",
                                  message="La evidencia documental de la fuente es obligatoria.")
        if s.fuente == FuentePrecio.ESTIMADA.value and len((s.justificacion_estimacion or "").strip()) < 50:  # FA-2
            raise BusinessRuleError(code="JUSTIFICACION_ESTIMACION_INSUFICIENTE", field="justificacion_estimacion", message=(
                "Para un precio estimado documente por qué no hay precio de mercado activo ni de UPRA y los comparables "
                "usados (mínimo 50 caracteres)."))
        if s.id_precio_corregido is not None and self.precios.obtener(s.id_precio_corregido) is None:
            raise NotFoundError(code="PRECIO_CORREGIDO_NO_ENCONTRADO", message="El precio que se corrige no existe.")
        if s.categoria == CategoriaPrecio.PRODUCTO.value:
            metrica = self.catalogo.metrica_produccion(s.id_metrica_produccion) if s.id_metrica_produccion else None
            if metrica is None or metrica["id_especie"] != s.id_especie:
                raise ValidationError(code="PRODUCTO_INVALIDO", field="id_metrica_produccion",
                                      message="Indique un producto (métrica de producción) de la especie.")
            return metrica["unidad_medida"]
        if s.id_metrica_produccion is not None:
            raise ValidationError(code="PRODUCTO_SOLO_EN_CATEGORIA_PRODUCTO", field="id_metrica_produccion",
                                  message="El producto solo aplica a precios de categoría producto.")
        return UNIDAD_POR_CATEGORIA[s.categoria]
