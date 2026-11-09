# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: DTO de entrada del módulo financiero |
# | 2026-11-09 | LuisfNarvaez01 | INC-M06-303-G04 RF-82/RF-84: costos manuales con máximo 4 decimales |
"""DTO de entrada de M06 (formato; las reglas de negocio están en los casos de uso)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import ConfigDict, Field, model_validator

from src.shared.base_dto import BaseDTO

TipoCierre = Literal["MENSUAL", "TRIMESTRAL", "ANUAL"]
Clasificacion = Literal["PRODUCCION", "CONSUMO"]
CategoriaActivo = Literal["PESO_KG", "POR_CABEZA"]
Categoria = Literal["PESO_KG", "POR_CABEZA", "PRODUCTO"]
Fuente = Literal["MERCADO_ACTIVO", "UPRA", "ESTIMADA"]
TipoHecho = Literal["RECONOCIMIENTO_NACIMIENTO", "RECONOCIMIENTO_DIFERENCIA", "VARIACION_VR_TB", "VARIACION_VR_PM",
                    "PRODUCTO_AGRICOLA", "CONSUMO_INSUMO", "MANO_OBRA_PROPIA", "BAJA_ACTIVO", "AJUSTE_PERIODO_ANTERIOR",
                    "DEPRECIACION_ACTIVO_COSTO", "DETERIORO_ACTIVO_COSTO"]
Sentido = Literal["GANANCIA", "PERDIDA", "UNICO", "TRASLADO", "CAPITALIZACION"]
Subtipo = Literal["ALIMENTO", "MEDICAMENTO", "MANO_OBRA", "VETERINARIO", "INVERSION_DIRECTA", "TRANSPORTE", "COMISION",
                  "IMPUESTO_TRANSACCION", "SACRIFICIO", "OTRO"]
Cuenta = Field(pattern=r"^[0-9]{1,20}$", description="Cuenta del plan contable (solo dígitos).")


class ConfiguracionContableDTO(BaseDTO):
    tipo_cierre: TipoCierre
    pct_umbral_desviacion_precio: Decimal = Field(gt=0, le=1000)
    dias_alerta_vencimiento_precio: Literal[7, 15, 30]


class ParametroEspecieDTO(BaseDTO):
    clasificacion: Clasificacion
    categoria_precio: CategoriaActivo = "PESO_KG"
    vida_util_meses: Optional[int] = Field(default=None, gt=0, le=1200)


class CostosVentaDTO(BaseDTO):
    """Porcentajes como fracción del valor bruto (0.02 = 2 %)."""

    pct_transporte: Decimal = Field(ge=0, le=1)
    pct_comisiones: Decimal = Field(ge=0, le=1)
    pct_impuestos: Decimal = Field(ge=0, le=1)


class AsignacionCuentaDTO(BaseDTO):
    tipo_hecho: TipoHecho
    sentido: Sentido
    id_especie: Optional[int] = Field(default=None, gt=0)
    subtipo_costo: Optional[Subtipo] = None
    cuenta_debito: str = Cuenta
    cuenta_credito: str = Cuenta

    @model_validator(mode="after")
    def _distintas(self):
        if self.cuenta_debito == self.cuenta_credito:
            raise ValueError("La cuenta débito y la cuenta crédito deben ser distintas.")
        return self


class PrecioDTO(BaseDTO):
    id_especie: int = Field(gt=0)
    categoria: Categoria
    id_metrica_produccion: Optional[int] = Field(default=None, gt=0)
    precio_unitario: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    fecha_vigencia: date
    fecha_vencimiento: Optional[date] = None
    fuente: Fuente
    evidencia_documental: str = Field(min_length=1, max_length=500)
    justificacion_estimacion: Optional[str] = Field(default=None, max_length=500)
    id_precio_corregido: Optional[int] = Field(default=None, gt=0)
    confirmar_desviacion: bool = False


class CostosManualesDTO(BaseDTO):
    # numeric(18,4): un 5.º decimal se rechaza (400) en vez de redondearse al guardar (INC-M06-303-G04).
    transporte: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    comisiones: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    impuestos: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    otros: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=4)


class ConfirmarReconocimientoDTO(BaseDTO):
    clasificacion: Optional[Clasificacion] = None
    costos_manuales: Optional[CostosManualesDTO] = None
    justificacion: Optional[str] = Field(default=None, max_length=1000,
                                         description="Obligatoria si se ingresan costos de venta manuales (RF-84 R2/R4).")

    @model_validator(mode="after")
    def _justificar_manuales(self):
        if self.costos_manuales and any(v is not None for v in self.costos_manuales.model_dump().values()) \
                and len((self.justificacion or "").strip()) < 20:
            raise ValueError("Los costos de venta manuales requieren una justificación con su soporte documental (mín. 20).")
        return self


class RevertirReconocimientoDTO(BaseDTO):
    motivo_reversion: str = Field(min_length=20, max_length=2000)


class CostoDTO(BaseDTO):
    subtipo_costo: Subtipo
    origen_costo: Literal["MANO_OBRA_PROPIA", "COMPRA_PROVEEDOR", "SERVICIO_TERCERO", "CONSUMO_INVENTARIO"]
    monto_costo: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    fecha_costo: date
    id_activo_biologico: Optional[int] = Field(default=None, gt=0)
    activos_reparto: list[int] = Field(default_factory=list, max_length=500)
    metodo_reparto: Literal["POR_CABEZAS", "POR_BIOMASA"] = "POR_CABEZAS"
    naturaleza_costo: Optional[Literal["MANTENIMIENTO", "INVERSION", "VENTA"]] = None
    justificacion: Optional[str] = Field(default=None, max_length=2000)
    tercero_nit: Optional[str] = Field(default=None, pattern=r"^[0-9]{6,15}$")
    tercero_dv: Optional[str] = Field(default=None, pattern=r"^[0-9]$")
    tercero_razon_social: Optional[str] = Field(default=None, max_length=200)
    factura_prefijo: Optional[str] = Field(default=None, max_length=10)
    factura_numero: Optional[str] = Field(default=None, max_length=30)
    fecha_factura: Optional[date] = None
    fecha_vencimiento_factura: Optional[date] = None
    cuenta_debito_manual: Optional[str] = Field(default=None, pattern=r"^[0-9]{1,20}$")
    confirmar_capitalizacion: bool = False

    # RF-90 CA-8: una solicitud con id_lote (u otro campo desconocido) se rechaza.
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ClasificarCostoDTO(BaseDTO):
    naturaleza_costo: Literal["MANTENIMIENTO", "INVERSION", "VENTA"]
    justificacion: str = Field(min_length=10, max_length=2000)


class CierreDTO(BaseDTO):
    autorizar_exclusiones: bool = False
    incluir_activos_sin_precio: bool = False


class DeterioroDTO(BaseDTO):
    id_evento_sanitario: int = Field(gt=0)
    impacto_economico_cop: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    justificacion: str = Field(min_length=30, max_length=2000)


class CotizacionDTO(BaseDTO):
    activos_cotizados: list[int] = Field(min_length=1, max_length=500)
    valor_cotizacion_propuesto: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    condiciones: Optional[str] = Field(default=None, max_length=2000)
    fecha_vencimiento: Optional[date] = None


class ModificarCotizacionDTO(BaseDTO):
    version: int = Field(ge=1)
    justificacion: str = Field(min_length=10, max_length=2000)
    valor_cotizacion_propuesto: Optional[Decimal] = Field(default=None, gt=0)
    condiciones: Optional[str] = Field(default=None, max_length=2000)
    fecha_vencimiento: Optional[date] = None


class AnularCotizacionDTO(BaseDTO):
    version: int = Field(ge=1)
    motivo_anulacion: str = Field(min_length=20, max_length=2000)


class FiltrosEstadoDTO(BaseDTO):
    id_especie: Optional[int] = Field(default=None, gt=0)
    id_activo_biologico: Optional[int] = Field(default=None, gt=0)
    id_infraestructura: Optional[int] = Field(default=None, gt=0)
    id_finca: Optional[int] = Field(default=None, gt=0)


class CompromisoDTO(BaseDTO):
    descripcion: str = Field(min_length=3, max_length=500)
    monto_estimado: Optional[Decimal] = None
    contraparte: Optional[str] = Field(default=None, max_length=200)
    fecha_estimada: Optional[date] = None


class PignoracionDTO(BaseDTO):
    id_activo_biologico: int = Field(gt=0)
    entidad_acreedora: str = Field(min_length=2, max_length=200)
    monto_garantia: Optional[Decimal] = None
    fecha_vencimiento: Optional[date] = None


class InformeRevelacionesDTO(BaseDTO):
    compromisos_vigentes: list[CompromisoDTO] = Field(default_factory=list)
    activos_pignorados: list[PignoracionDTO] = Field(default_factory=list)
    declaracion_sin_novedad: bool = False
    justificacion_inconsistencias: Optional[str] = Field(default=None, max_length=2000)


class ResolverInformeDTO(BaseDTO):
    aprobar: bool
    razon_rechazo: Optional[str] = Field(default=None, max_length=2000)
