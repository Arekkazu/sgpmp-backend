# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: endpoints del módulo financiero NIC 41 (/finanzas) |
# | 2026-11-05 | Arekkazu | M06 RF-83..94: listados del período y filtros validados para las vistas del prototipo |
# | 2026-11-08 | Arekkazu | INC-M06-314-G15 RF-83 / INC-M06-330-G86 RF-94: filtros de mediciones y de auditoría |
# | 2026-11-08 | destroyerban | INC-M06-306-G07 RF-82: los 403 de RBAC quedan en la auditoría financiera |
# | 2026-11-08 | destroyerban | INC-M06-316-G16 RF-84: referencia documental de los costos manuales |
# | 2026-11-09 | destroyerban | INC-M06-317-G17 RF-84: cálculo en revisión y validación del valor neto ≤ 0 |
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
# | 2026-11-09 | destroyerban | INC-M06-325-G30 RF-85 RNF-85-05: historial de productos con filtros, evento y usuario |
# | 2026-11-10 | Arekkazu | INC-M06-337/345/350/351 RF-86/87: acumulado, cancelar cierre, ajuste y 403 con el rol |
# | 2026-11-10 | destroyerban | INC-M06-336-G36 RF-86: correctivo de variaciones con aprobación del Contador |
# | 2026-11-10 | Arekkazu | Lote M05/M06 RF-82/87: el 403 nombra el rol y queda en la auditoría financiera (#1025 + #1068) |
# | 2026-11-10 | Arekkazu | INC-M06-297-G34 RF-86: eventos del período con medición pendiente |
# | 2026-11-10 | Arekkazu | INC-M06-346-G43-03 RF-87 FA-2: el cierre recibe la decisión por activo sin precio |
# | 2026-11-10 | Arekkazu | TC-DIS-262 RF-93: los períodos los lee quien consulta el estado de resultados o las revelaciones |
# | 2026-11-11 | Arekkazu | TC-M06-G106 RF-89 FA-6: estado corregido en el historial de precios |
# | 2026-11-11 | Arekkazu | USAB-M06 M6-03 RF-82/87: listas del período filtradas por el titular (NIT validado) |
# | 2026-11-11 | Arekkazu | USAB-M06 RF-87/93: titulares con período, filtro sin titular y último cierre de todos los períodos en una consulta |
# | 2026-11-12 | Arekkazu | TC-DIS-256 RF-91: las líneas también las lee quien solo consulta la trazabilidad (auditor externo) |
# | 2026-11-13 | Arekkazu | QA-M06 CU13 H-02 C3 RF-94: autores de la bitácora por nombre |
"""Routers de M06 (``/finanzas``). Sin lógica: arman el caso de uso con la fábrica y lo ejecutan.

Autorización por RBAC (``require_permission_sobre``, cuyo 403 queda en RF-94 vía
``require_permission_m06``), recursos por nombre (ids 88-99 de la
migración ``c4d81e6f2a95``) y acciones C=1, R=2, U=3, D=4, E=5. El Contador tiene acceso completo;
el Administrador, el Productor y el Revisor Fiscal, el que les da la matriz de esa migración."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import SolicitudCosto
from src.financial_valuation.application.use_cases.precios.registrar_precio_use_case import SolicitudPrecio
from src.financial_valuation.domain.entities.contabilidad import ParametroEspecie
from src.financial_valuation.infrastructure.dto.m06_dto import (
    AjustePeriodoAnteriorDTO,
    AnularCotizacionDTO,
    AsignacionCuentaDTO,
    CierreDTO,
    ClasificarCostoDTO,
    ConfiguracionContableDTO,
    ConfirmarReconocimientoDTO,
    CostoDTO,
    CostosVentaDTO,
    CotizacionDTO,
    DeterioroDTO,
    FiltrosEstadoDTO,
    InformeRevelacionesDTO,
    ModificarCotizacionDTO,
    ParametroEspecieDTO,
    PrecioDTO,
    ReconocerCosechaDTO,
    ResolverInformeDTO,
    RechazarCorrectivoDTO,
    RevertirReconocimientoDTO,
    SolicitarCorrectivoDTO,
    ValidarCalculoDTO,
)
from src.financial_valuation.infrastructure.factories.m06_factory import M06
from src.financial_valuation.infrastructure.rbac_auditoria import require_alguno_m06, require_permission_m06
from src.identity_access.infrastructure.dependencies import UsuarioActual, get_current_user
from src.shared.database import get_db
from src.shared.errors import ConflictError, NotFoundError
from src.shared.fechas import hoy_usuario
from src.shared.schemas import ErrorResponse

C, R, U, D, E = 1, 2, 3, 4, 5
_DENEGADO = "Acceso denegado: su rol ({rol}) no tiene permiso para esta operación del módulo financiero."
_DENEGADO_CIERRE = ("Acceso denegado: el cierre del período contable es competencia exclusiva del Contador. "
                    "Su rol actual ({rol}) no tiene permisos de cierre contable.")


def permiso(recurso: str, accion: int, mensaje: str = _DENEGADO):
    """RBAC por nombre de recurso: el 403 nombra el rol del usuario (RF-87 FA-4) y queda en RF-94 (RNF-82-05)."""
    return require_permission_m06(recurso, accion, mensaje_denegado=mensaje)


# Catálogos de los filtros: un valor fuera de ellos responde 400 en vez de una lista vacía silenciosa.
Clasificacion = Literal["PRODUCCION", "CONSUMO"]
EstadoLinea = Literal["PENDIENTE_CUENTA", "REGISTRADA", "VERIFICACION_PENDIENTE", "VERIFICADO", "PENDIENTE_TRAZABILIDAD"]
EstadoCosto = Literal["REGISTRADO", "PENDIENTE_CLASIFICACION"]
OrigenCosto = Literal["CONSUMO_INVENTARIO", "MANO_OBRA_PROPIA", "COMPRA_PROVEEDOR", "SERVICIO_TERCERO"]
NaturalezaCosto = Literal["MANTENIMIENTO", "INVERSION", "VENTA"]
SubtipoCosto = Literal["ALIMENTO", "MEDICAMENTO", "MANO_OBRA", "VETERINARIO", "TRANSPORTE", "COMISION",
                       "IMPUESTO_TRANSACCION", "SACRIFICIO", "INVERSION_DIRECTA", "OTRO"]
EstadoCotizacion = Literal["COTIZADO", "VENCIDA", "ANULADA", "CONVERTIDA_EN_VENTA"]
Severidad = Literal["INFO", "WARNING", "ERROR", "CRITICAL"]
TipoProducto = Literal["PRODUCTO_DE_CONSUMO", "PRODUCTO_PERIODICO"]
EstadoCorrectivo = Literal["PENDIENTE", "APROBADA", "RECHAZADA"]
_ERRORES = {c: {"model": ErrorResponse} for c in (400, 401, 403, 404, 409, 412, 422, 500)}

router = APIRouter(prefix="/finanzas", responses=_ERRORES)


def _m06(db: Session = Depends(get_db)) -> M06:
    return M06(db)


def _descarga(contenido: bytes, tipo: str, extension: str, nombre: str) -> Response:
    return Response(content=contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}.{extension}"'})


# --- Configuración contable (RF-84, RF-88, RF-109) ------------------------------------------------

TAG_CONFIG = "M06 · Configuración contable"


@router.get("/configuracion", tags=[TAG_CONFIG], dependencies=[Depends(permiso("configuracion_contable", R))],
            summary="Configuración contable completa (periodicidad, especies, costos de venta, matriz)")
def consultar_configuracion(m: M06 = Depends(_m06)) -> dict:
    return {"general": m.config.obtener().__dict__, "especies": m.config.listar_parametros_especie(),
            "costos_venta": m.config.listar_costos_venta(),
            "matriz": [a.__dict__ for a in m.config.listar_asignaciones()],
            "lineas_pendientes_cuenta": len(m.asientos.pendientes_de_cuenta())}


@router.put("/configuracion", tags=[TAG_CONFIG], dependencies=[Depends(permiso("configuracion_contable", U))],
            summary="Actualizar periodicidad del cierre, umbral de desviación de precio y alertas de vencimiento")
def actualizar_configuracion(dto: ConfiguracionContableDTO, m: M06 = Depends(_m06),
                             usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.actualizar_configuracion().execute(dto.tipo_cierre, dto.pct_umbral_desviacion_precio,
                                                dto.dias_alerta_vencimiento_precio, usuario.id_usuario).__dict__


@router.put("/configuracion/especies/{id_especie}", tags=[TAG_CONFIG],
            dependencies=[Depends(permiso("configuracion_contable", U))],
            summary="Clasificación (producción/consumo), categoría de precio y vida útil de una especie")
def guardar_parametro_especie(id_especie: int, dto: ParametroEspecieDTO, m: M06 = Depends(_m06),
                              usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    parametro = ParametroEspecie(id_especie, dto.clasificacion, dto.categoria_precio, dto.vida_util_meses)
    return m.guardar_parametro_especie().execute(parametro, usuario.id_usuario).__dict__


@router.put("/configuracion/costos-venta/{id_especie}", tags=[TAG_CONFIG],
            dependencies=[Depends(permiso("configuracion_contable", U))],
            summary="Costos de venta parametrizados de una especie (fracciones del valor bruto)")
def guardar_costos_venta(id_especie: int, dto: CostosVentaDTO, m: M06 = Depends(_m06),
                         usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    nuevo = m.guardar_costos_venta().execute(id_especie, dto.pct_transporte, dto.pct_comisiones, dto.pct_impuestos,
                                             usuario.id_usuario)
    return {"id_parametro_costo_venta": nuevo}


@router.post("/configuracion/matriz", tags=[TAG_CONFIG], status_code=201,
             dependencies=[Depends(permiso("configuracion_contable", C))],
             summary="Asignar el par de cuentas de un hecho contable (resuelve las líneas pendientes de cuenta)")
def guardar_asignacion(dto: AsignacionCuentaDTO, m: M06 = Depends(_m06),
                       usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.guardar_asignacion().execute(dto.tipo_hecho, dto.sentido, dto.id_especie, dto.subtipo_costo,
                                          dto.cuenta_debito, dto.cuenta_credito, usuario.id_usuario)


@router.delete("/configuracion/matriz/{id_asignacion}", tags=[TAG_CONFIG], status_code=204,
               dependencies=[Depends(permiso("configuracion_contable", U))], summary="Desactivar una asignación de cuentas")
def desactivar_asignacion(id_asignacion: int, m: M06 = Depends(_m06),
                          usuario: UsuarioActual = Depends(get_current_user)) -> Response:
    m.guardar_asignacion().desactivar(id_asignacion, usuario.id_usuario)
    return Response(status_code=204)


# --- Precios de mercado (RF-89) ---------------------------------------------------------------------

TAG_PRECIOS = "M06 · Precios de mercado"


@router.get("/precios", tags=[TAG_PRECIOS], dependencies=[Depends(permiso("precios_mercado", R))],
            summary="Historial de precios con su estado (vigente, programado, vencido, superado, corregido)")
def listar_precios(id_especie: Optional[int] = Query(None, gt=0), m: M06 = Depends(_m06)) -> list[dict]:
    return m.listar_precios().execute(id_especie)


@router.post("/precios", tags=[TAG_PRECIOS], status_code=201, dependencies=[Depends(permiso("precios_mercado", C))],
             summary="Registrar un precio de mercado de referencia o la corrección de uno (append-only)")
def registrar_precio(dto: PrecioDTO, m: M06 = Depends(_m06), usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.registrar_precio().execute(SolicitudPrecio(**dto.model_dump()), usuario.id_usuario)


# --- Reconocimiento inicial (RF-82, RF-88 escenario A) ------------------------------------------------

# Titular del período (RF-19): las listas del período muestran solo sus activos. Mismo formato que en M07.
_NIT_TITULAR = Query(None, pattern=r"^[0-9]{6,15}$", description="NIT del titular, solo dígitos y sin dígito de verificación.")

TAG_RECON = "M06 · Reconocimiento inicial"


@router.get("/reconocimientos/propuestas", tags=[TAG_RECON], dependencies=[Depends(permiso("reconocimiento_inicial", R))],
            summary="Propuestas de reconocimiento de los activos sin reconocimiento confirmado")
def listar_propuestas(numero_id_tributaria: Optional[str] = _NIT_TITULAR, m: M06 = Depends(_m06),
                      usuario: UsuarioActual = Depends(get_current_user)) -> list[dict]:
    return m.propuestas().execute(usuario.id_usuario, numero_id_tributaria)


@router.get("/reconocimientos/propuestas/{id_activo_biologico}", tags=[TAG_RECON],
            dependencies=[Depends(permiso("reconocimiento_inicial", R))], summary="Propuesta de un activo")
def propuesta_activo(id_activo_biologico: int, clasificacion: Optional[Clasificacion] = None, m: M06 = Depends(_m06),
                     usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.propuestas().de_activo(id_activo_biologico, usuario.id_usuario, clasificacion=clasificacion)


@router.post("/reconocimientos/{id_activo_biologico}", tags=[TAG_RECON], status_code=201,
             dependencies=[Depends(permiso("reconocimiento_inicial", C))],
             summary="Confirmar el reconocimiento inicial del activo (genera sus líneas de asiento)")
def confirmar_reconocimiento(id_activo_biologico: int, dto: ConfirmarReconocimientoDTO, m: M06 = Depends(_m06),
                             usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    manuales = dto.costos_manuales.model_dump() if dto.costos_manuales else None
    return m.confirmar_reconocimiento().execute(id_activo_biologico, usuario.id_usuario, clasificacion=dto.clasificacion,
                                                costos_manuales=manuales, justificacion=dto.justificacion,
                                                referencia_documental=dto.referencia_documental)


@router.post("/reconocimientos/{id_activo_biologico}/reversion", tags=[TAG_RECON],
             dependencies=[Depends(permiso("reconocimiento_inicial", D))],
             summary="Revertir el reconocimiento inicial (asiento espejo; solo sin registros dependientes)")
def revertir_reconocimiento(id_activo_biologico: int, dto: RevertirReconocimientoDTO, m: M06 = Depends(_m06),
                            usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.revertir_reconocimiento().execute(id_activo_biologico, dto.motivo_reversion, usuario.id_usuario)


# --- Valoración de activos (RF-83 a RF-86) -------------------------------------------------------------

TAG_VALOR = "M06 · Valoración de activos"


@router.get("/activos", tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Activos reconocidos con su valor en libros y método de valoración")
def listar_activos_valorados(numero_id_tributaria: Optional[str] = _NIT_TITULAR, m: M06 = Depends(_m06)) -> list[dict]:
    return m.valoraciones.activos_valorados(numero_id_tributaria)


@router.get("/activos/{id_activo_biologico}", tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Historial financiero del activo: reconocimientos, cálculos, mediciones, productos y líneas")
def historial_activo(id_activo_biologico: int, m: M06 = Depends(_m06)) -> dict:
    activo = m.activos.obtener(id_activo_biologico)
    if activo is None:
        raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe.")
    return {"activo": activo.__dict__, **m.valoraciones.historial_activo(id_activo_biologico),
            "lineas": [ln.__dict__ for ln in m.asientos.del_activo(id_activo_biologico)]}


@router.get("/activos/{id_activo_biologico}/simulacion", tags=[TAG_VALOR],
            dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Valor razonable menos costos de venta a hoy, sin registrarlo (solicitud directa de RF-84)")
def simular_valor(id_activo_biologico: int, m: M06 = Depends(_m06), usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    activo = m.activos.obtener(id_activo_biologico)
    if activo is None:
        raise NotFoundError(code="ACTIVO_NO_ENCONTRADO", message="El activo biológico no existe.")
    resultado = m.valorador.valorar(activo, hoy_usuario(), 0, usuario.id_usuario, aceptar_no_positivo=True)
    return {"es_valido": resultado.es_valido, "motivo": resultado.motivo, "mensaje": resultado.mensaje,
            "calculo": resultado.calculo.__dict__ if resultado.calculo else None,
            "precio": resultado.precio.__dict__ if resultado.precio else None}


@router.post("/calculos/{id_calculo_valor_razonable}/validacion", tags=[TAG_VALOR],
             dependencies=[Depends(permiso("valoracion_activos", E))],
             summary="Validar con justificación un cálculo con valor neto ≤ 0 (REVISION_REQUERIDA → CALCULADO)")
def validar_calculo(id_calculo_valor_razonable: int, dto: ValidarCalculoDTO, m: M06 = Depends(_m06),
                    usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.validar_calculo().execute(id_calculo_valor_razonable, dto.justificacion, usuario.id_usuario)


@router.post("/eventos/procesar", tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", E))],
             summary="Procesar ya los eventos de M02 pendientes (lo hace también el proceso de fondo)")
def procesar_eventos(m: M06 = Depends(_m06)) -> dict:
    return {"eventos": m.procesar_eventos().execute(500), "provisiones_m05": m.procesar_provisiones().execute(500)}


@router.get("/productos/pendientes", tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Cosechas cuyo reconocimiento quedó pendiente por falta de precio o de costos de venta (RF-85)")
def cosechas_pendientes(m: M06 = Depends(_m06)) -> list[dict]:
    return m.eventos.cosechas_pendientes()


@router.post("/productos/pendientes/{id_evento}/reconocimiento", tags=[TAG_VALOR],
             dependencies=[Depends(permiso("valoracion_activos", E))],
             summary="Reconocer una cosecha pendiente con costos de venta ingresados a mano (RF-85 FA-2)")
def reconocer_cosecha_pendiente(id_evento: int, dto: ReconocerCosechaDTO, m: M06 = Depends(_m06),
                                usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    manuales = dto.costos_manuales.model_dump() if dto.costos_manuales else None
    return m.reconocer_cosecha_pendiente().execute(id_evento, manuales, dto.justificacion, usuario.id_usuario)


# TC-DIS-256 / RF-91: también las lee quien solo consulta la trazabilidad (el auditor externo); la RLS de
# `lineas_asiento_nic41` le muestra únicamente las de períodos cerrados.
@router.get("/lineas", tags=[TAG_VALOR],
            dependencies=[Depends(require_alguno_m06([("valoracion_activos", R), ("trazabilidad_contable", R)],
                                                     mensaje_denegado=_DENEGADO))],
            summary="Líneas de asiento NIC 41 de un período (filtrables por estado)")
def listar_lineas(id_periodo_contable: int = Query(gt=0), estado: Optional[EstadoLinea] = None,
                  m: M06 = Depends(_m06)) -> list[dict]:
    lineas = m.asientos.del_periodo(id_periodo_contable)
    return [{**ln.__dict__, **ln.extra} for ln in lineas if estado is None or ln.estado == estado
            or ln.extra.get("estado_trazabilidad") == estado]


@router.get("/periodos/{id_periodo_contable}/mediciones", tags=[TAG_VALOR],
            dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Mediciones posteriores del período con el activo medido (filtrables por evento y estimación)")
def mediciones_del_periodo(id_periodo_contable: int, id_evento: Optional[int] = Query(None, gt=0),
                           tiene_valor_estimado: Optional[bool] = None, m: M06 = Depends(_m06)) -> list[dict]:
    return m.valoraciones.mediciones_del_periodo(id_periodo_contable, id_evento=id_evento,
                                                 tiene_valor_estimado=tiene_valor_estimado)


@router.get("/periodos/{id_periodo_contable}/eventos-pendientes", tags=[TAG_VALOR],
            dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Eventos del período cuya medición quedó pendiente; no dejan medición posterior (RF-86)")
def eventos_pendientes_del_periodo(id_periodo_contable: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.valoraciones.eventos_pendientes_del_periodo(id_periodo_contable)


@router.get("/periodos/{id_periodo_contable}/variaciones", tags=[TAG_VALOR],
            dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Variaciones de valor razonable del período con su evidencia y trazabilidad")
def variaciones_del_periodo(id_periodo_contable: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.valoraciones.variaciones_del_periodo(id_periodo_contable)


# --- Correctivos de variaciones (RF-86 restricción 5, CA-12, CA-13) ---------------------------------------

_INMUTABLE = ("Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. "
              "Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia "
              "el original, y se aplicará cuando otro Contador lo apruebe.")


@router.post("/variaciones/{id_variacion}/correctivos", tags=[TAG_VALOR], status_code=201,
             dependencies=[Depends(permiso("valoracion_activos", E))],
             summary="Solicitar el correctivo de una variación (monto opuesto; queda pendiente de aprobación)")
def solicitar_correctivo(id_variacion: int, dto: SolicitarCorrectivoDTO, m: M06 = Depends(_m06),
                         usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.solicitar_correctivo().execute(id_variacion, dto.motivo, usuario.id_usuario)


@router.get("/correctivos", tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Solicitudes de correctivo de variaciones (filtrables por estado, período y activo)")
def listar_correctivos(estado: Optional[EstadoCorrectivo] = None, id_periodo_contable: Optional[int] = Query(None, gt=0),
                       id_activo_biologico: Optional[int] = Query(None, gt=0), m: M06 = Depends(_m06)) -> list[dict]:
    return m.correctivos.listar({"estado": estado, "id_periodo_contable": id_periodo_contable,
                                 "id_activo_biologico": id_activo_biologico})


@router.post("/correctivos/{id_solicitud}/aprobacion", tags=[TAG_VALOR],
             dependencies=[Depends(permiso("valoracion_activos", E))],
             summary="Aprobar un correctivo: registra la variación correctiva y sus líneas inversas (otro Contador)")
def aprobar_correctivo(id_solicitud: int, m: M06 = Depends(_m06), usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.resolver_correctivo().aprobar(id_solicitud, usuario.id_usuario)


@router.post("/correctivos/{id_solicitud}/rechazo", tags=[TAG_VALOR],
             dependencies=[Depends(permiso("valoracion_activos", E))],
             summary="Rechazar un correctivo pendiente con su motivo (otro Contador)")
def rechazar_correctivo(id_solicitud: int, dto: RechazarCorrectivoDTO, m: M06 = Depends(_m06),
                        usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.resolver_correctivo().rechazar(id_solicitud, dto.motivo_rechazo, usuario.id_usuario)


@router.api_route("/variaciones/{id_variacion}", methods=["PUT", "PATCH", "DELETE"], tags=[TAG_VALOR],
                  dependencies=[Depends(permiso("valoracion_activos", R))], include_in_schema=False)
@router.api_route("/periodos/{id_periodo_contable}/variaciones/{id_variacion}", methods=["PUT", "PATCH", "DELETE"],
                  tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", R))], include_in_schema=False)
def variacion_inmutable(id_variacion: int) -> None:
    """CA-12: la modificación directa se rechaza y orienta al correctivo (``POST /variaciones/{id}/correctivos``)."""
    raise ConflictError(code="VARIACION_INMUTABLE", message=_INMUTABLE)


@router.api_route("/lineas/{id_linea}", methods=["PUT", "PATCH", "DELETE"], tags=[TAG_VALOR],
                  dependencies=[Depends(permiso("valoracion_activos", R))], include_in_schema=False)
def linea_inmutable(id_linea: int) -> None:
    """Las líneas de asiento tampoco se modifican: se corrigen con líneas inversas del correctivo o de la reversión."""
    raise ConflictError(code="LINEA_ASIENTO_INMUTABLE", message=(
        "Las líneas de asiento no se modifican ni se eliminan. Si la línea viene de una variación errónea, solicite el "
        "correctivo de esa variación: al aprobarse se registra la línea inversa. Un reconocimiento inicial se corrige "
        "con su reversión."))


@router.get("/periodos/{id_periodo_contable}/calculos", tags=[TAG_VALOR],
            dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Cálculos del valor razonable menos costos de venta registrados en el período")
def calculos_del_periodo(id_periodo_contable: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.valoraciones.calculos_del_periodo(id_periodo_contable)


def _filtros_productos(tipo: Optional[TipoProducto] = None, id_activo_biologico: Optional[int] = Query(None, gt=0),
                       id_especie: Optional[int] = Query(None, gt=0),
                       producto_agricola: Optional[str] = Query(None, min_length=1, max_length=100),
                       valor_min: Optional[Decimal] = Query(None, ge=0, max_digits=18, decimal_places=4),
                       valor_max: Optional[Decimal] = Query(None, ge=0, max_digits=18, decimal_places=4)) -> dict:
    return {"tipo": tipo, "id_activo_biologico": id_activo_biologico, "id_especie": id_especie,
            "producto_agricola": producto_agricola, "valor_min": valor_min, "valor_max": valor_max}


@router.get("/periodos/{id_periodo_contable}/productos", tags=[TAG_VALOR],
            dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Productos agrícolas reconocidos en el período (filtrables por tipo, activo, especie, producto y valor)")
def productos_del_periodo(id_periodo_contable: int, filtros: dict = Depends(_filtros_productos),
                          m: M06 = Depends(_m06)) -> list[dict]:
    return m.consultar_productos().execute({**filtros, "id_periodo_contable": id_periodo_contable})


@router.get("/productos", tags=[TAG_VALOR], dependencies=[Depends(permiso("valoracion_activos", R))],
            summary="Historial de productos agrícolas reconocidos (RNF-85-05: activo, período, tipo y rango de valores)")
def historial_productos(id_periodo_contable: Optional[int] = Query(None, gt=0), filtros: dict = Depends(_filtros_productos),
                        m: M06 = Depends(_m06)) -> list[dict]:
    return m.consultar_productos().execute({**filtros, "id_periodo_contable": id_periodo_contable})


# --- Costos (RF-90) ---------------------------------------------------------------------------------------

TAG_COSTOS = "M06 · Costos"


@router.get("/costos", tags=[TAG_COSTOS], dependencies=[Depends(permiso("costos_activos", R))], summary="Listar costos")
def listar_costos(id_activo_biologico: Optional[int] = Query(None, gt=0), id_periodo_contable: Optional[int] = Query(None, gt=0),
                  estado: Optional[EstadoCosto] = None, origen_costo: Optional[OrigenCosto] = None,
                  naturaleza_costo: Optional[NaturalezaCosto] = None, subtipo_costo: Optional[SubtipoCosto] = None,
                  id_especie: Optional[int] = Query(None, gt=0), m: M06 = Depends(_m06)) -> list[dict]:
    return m.costos.listar({"id_activo_biologico": id_activo_biologico, "id_periodo_contable": id_periodo_contable,
                            "estado": estado, "origen_costo": origen_costo, "naturaleza_costo": naturaleza_costo,
                            "subtipo_costo": subtipo_costo, "id_especie": id_especie})


@router.post("/costos", tags=[TAG_COSTOS], status_code=201, dependencies=[Depends(permiso("costos_activos", C))],
             summary="Registrar un costo manual (con reparto y factura de proveedor si aplica)")
def registrar_costo(dto: CostoDTO, m: M06 = Depends(_m06), usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.registrar_costo().execute(SolicitudCosto(**dto.model_dump()), usuario.id_usuario)


@router.post("/costos/{id_registro_costo}/clasificacion", tags=[TAG_COSTOS],
             dependencies=[Depends(permiso("costos_activos", U))], summary="Clasificar un costo pendiente")
def clasificar_costo(id_registro_costo: int, dto: ClasificarCostoDTO, m: M06 = Depends(_m06),
                     usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.clasificar_costo().execute(id_registro_costo, dto.naturaleza_costo, dto.justificacion, usuario.id_usuario)


# --- Períodos y cierre (RF-87) ---------------------------------------------------------------------------

TAG_CIERRE = "M06 · Períodos y cierre"


# Leen períodos quien cierra y quien solo consulta los reportes del período (el Productor, RF-93).
_LEE_PERIODOS = Depends(require_alguno_m06([("cierre_periodo", R), ("estado_resultados", R), ("revelaciones_nic41", R)],
                                           mensaje_denegado=_DENEGADO))


@router.get("/titulares", tags=[TAG_CIERRE], dependencies=[_LEE_PERIODOS],
            summary="Titulares (NIT y razón social) con períodos contables, para elegir primero el titular")
def listar_titulares(m: M06 = Depends(_m06)) -> list[dict]:
    return m.periodos.titulares()


@router.get("/periodos", tags=[TAG_CIERRE], dependencies=[_LEE_PERIODOS],
            summary="Períodos contables por titular con su último cierre (también para quien solo consulta reportes)")
def listar_periodos(numero_id_tributaria: Optional[str] = _NIT_TITULAR,
                    sin_titular: bool = Query(False, description="Solo los períodos sin titular asignado; ignora el NIT."),
                    m: M06 = Depends(_m06)) -> list[dict]:
    periodos = m.periodos.listar(numero_id_tributaria, sin_titular)
    cierres = m.periodos.ultimas_ejecuciones([p.id_periodo_contable for p in periodos])
    return [{**p.__dict__, "ultimo_cierre": cierres.get(p.id_periodo_contable)} for p in periodos]


@router.get("/periodos/{id_periodo_contable}/prevalidacion", tags=[TAG_CIERRE],
            dependencies=[Depends(permiso("cierre_periodo", R))],
            summary="Qué bloquea o exige autorización antes de cerrar el período")
def prevalidar_cierre(id_periodo_contable: int, m: M06 = Depends(_m06)) -> dict:
    periodo = m.periodos.obtener(id_periodo_contable)
    if periodo is None:
        raise NotFoundError(code="PERIODO_NO_ENCONTRADO", message="El período contable no existe.")
    return m.cierre().prevalidar(periodo).a_dict()


@router.post("/periodos/{id_periodo_contable}/cierre", tags=[TAG_CIERRE],
             dependencies=[Depends(permiso("cierre_periodo", E, _DENEGADO_CIERRE))],
             summary="Ejecutar el cierre del período (revaluación, comprobante NIC 41, estado de resultados)")
def ejecutar_cierre(id_periodo_contable: int, dto: CierreDTO, m: M06 = Depends(_m06),
                    usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.cierre().execute(id_periodo_contable, usuario.id_usuario, autorizar_exclusiones=dto.autorizar_exclusiones,
                              incluir_activos_sin_precio=dto.incluir_activos_sin_precio,
                              activos_estimados=dto.activos_estimados)


@router.post("/periodos/{id_periodo_contable}/cierre/cancelacion", tags=[TAG_CIERRE],
             dependencies=[Depends(permiso("cierre_periodo", E, _DENEGADO_CIERRE))],
             summary="Cancelar el cierre que espera autorización de exclusiones (el período vuelve a ABIERTO)")
def cancelar_cierre(id_periodo_contable: int, m: M06 = Depends(_m06),
                    usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.cierre().cancelar(id_periodo_contable, usuario.id_usuario)


@router.post("/lineas-asiento/{id_linea}/ajustes", tags=[TAG_CIERRE], status_code=201,
             dependencies=[Depends(permiso("cierre_periodo", E))],
             summary="Corregir un hecho de un período cerrado con un ajuste en el período abierto")
def registrar_ajuste_periodo_anterior(id_linea: int, dto: AjustePeriodoAnteriorDTO, m: M06 = Depends(_m06),
                                      usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.ajuste_periodo_anterior().execute(id_linea, dto.tipo_ajuste, dto.valor, dto.justificacion,
                                               usuario.id_usuario)


@router.get("/periodos/{id_periodo_contable}/comprobantes", tags=[TAG_CIERRE],
            dependencies=[Depends(permiso("cierre_periodo", R))], summary="Comprobantes NIC 41 del período")
def comprobantes(id_periodo_contable: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.periodos.comprobantes(id_periodo_contable)


@router.get("/periodos/{id_periodo_contable}/comprobantes/descarga", tags=[TAG_CIERRE],
            dependencies=[Depends(permiso("cierre_periodo", R))], summary="Descargar el comprobante (csv o pdf)")
def descargar_comprobantes(id_periodo_contable: int, formato: str = Query("csv", pattern="^(csv|pdf|excel)$"),
                           m: M06 = Depends(_m06)) -> Response:
    return _descarga(*m.exportar().comprobantes(id_periodo_contable, formato))


# --- Valoración por costo (RF-88) ----------------------------------------------------------------------------

TAG_COSTO = "M06 · Valoración por costo"


@router.get("/activos/{id_activo_biologico}/eventos-sanitarios", tags=[TAG_COSTO],
            dependencies=[Depends(permiso("valoracion_por_costo", R))],
            summary="Eventos sanitarios del activo, para elegir el que sustenta un deterioro")
def eventos_sanitarios(id_activo_biologico: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.activos.eventos_sanitarios_del_activo(id_activo_biologico)


@router.post("/activos/{id_activo_biologico}/deterioros", tags=[TAG_COSTO], status_code=201,
             dependencies=[Depends(permiso("valoracion_por_costo", C))],
             summary="Registrar el deterioro de un activo valorado por costo (evento sanitario)")
def registrar_deterioro(id_activo_biologico: int, dto: DeterioroDTO, m: M06 = Depends(_m06),
                        usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.registrar_deterioro().execute(id_activo_biologico, dto.id_evento_sanitario, dto.impacto_economico_cop,
                                           dto.justificacion, usuario.id_usuario)


@router.post("/activos/{id_activo_biologico}/valor-razonable", tags=[TAG_COSTO],
             dependencies=[Depends(permiso("valoracion_por_costo", U))],
             summary="Pasar del modelo de costo a valor razonable (NIC 41 ¶30)")
def cambiar_a_valor_razonable(id_activo_biologico: int, m: M06 = Depends(_m06),
                              usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.cambiar_a_valor_razonable().execute(id_activo_biologico, usuario.id_usuario)


# --- Cotizaciones (RF-COT) -----------------------------------------------------------------------------------

TAG_COT = "M06 · Cotizaciones"


@router.get("/cotizaciones", tags=[TAG_COT], dependencies=[Depends(permiso("cotizaciones", R))], summary="Listar cotizaciones")
def listar_cotizaciones(estado: Optional[EstadoCotizacion] = None, id_activo_biologico: Optional[int] = Query(None, gt=0),
                        m: M06 = Depends(_m06)) -> list[dict]:
    return m.cotizaciones.listar({"estado": estado, "id_activo_biologico": id_activo_biologico})


@router.post("/cotizaciones", tags=[TAG_COT], status_code=201, dependencies=[Depends(permiso("cotizaciones", C))],
             summary="Registrar una cotización de venta (no tiene efecto contable)")
def registrar_cotizacion(dto: CotizacionDTO, m: M06 = Depends(_m06), usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.registrar_cotizacion().execute(dto.activos_cotizados, dto.valor_cotizacion_propuesto, dto.condiciones,
                                            dto.fecha_vencimiento, usuario.id_usuario)


@router.patch("/cotizaciones/{id_cotizacion}", tags=[TAG_COT], dependencies=[Depends(permiso("cotizaciones", U))],
              summary="Modificar valor propuesto, condiciones o vencimiento (control por versión)")
def modificar_cotizacion(id_cotizacion: int, dto: ModificarCotizacionDTO, m: M06 = Depends(_m06),
                         usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    cambios = dto.model_dump(exclude_unset=True, exclude={"version", "justificacion"})
    return m.modificar_cotizacion().modificar(id_cotizacion, dto.version, cambios, dto.justificacion, usuario.id_usuario)


@router.post("/cotizaciones/{id_cotizacion}/anulacion", tags=[TAG_COT], dependencies=[Depends(permiso("cotizaciones", D))],
             summary="Anular una cotización (irrevocable)")
def anular_cotizacion(id_cotizacion: int, dto: AnularCotizacionDTO, m: M06 = Depends(_m06),
                      usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.modificar_cotizacion().anular(id_cotizacion, dto.version, dto.motivo_anulacion, usuario.id_usuario)


# --- Trazabilidad (RF-91) ---------------------------------------------------------------------------------------

TAG_TRAZA = "M06 · Trazabilidad contable"


@router.post("/periodos/{id_periodo_contable}/trazabilidad", tags=[TAG_TRAZA],
             dependencies=[Depends(permiso("trazabilidad_contable", E))],
             summary="Verificar la cadena de trazabilidad de las líneas del período")
def verificar_trazabilidad(id_periodo_contable: int, m: M06 = Depends(_m06),
                           usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.verificar_trazabilidad().execute(id_periodo_contable, usuario.id_usuario)


@router.get("/lineas/{id_linea}/cadena", tags=[TAG_TRAZA], dependencies=[Depends(permiso("trazabilidad_contable", R))],
            summary="Cadena navegable de una línea: evidencia, evento, valoración y asiento")
def cadena(id_linea: int, m: M06 = Depends(_m06)) -> dict:
    resultado = m.trazabilidad.cadena(id_linea)
    if resultado is None:
        raise NotFoundError(code="LINEA_NO_ENCONTRADA", message="La línea de asiento no existe.")
    return resultado


# --- Revelaciones (RF-92) y estado de resultados (RF-93) ---------------------------------------------------------

TAG_REP = "M06 · Revelaciones y estado de resultados"


@router.get("/periodos/{id_periodo_contable}/estados-resultados", tags=[TAG_REP],
            dependencies=[Depends(permiso("estado_resultados", R))], summary="Versiones del estado de resultados")
def listar_estados(id_periodo_contable: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.reportes.listar_estados(id_periodo_contable)


@router.get("/periodos/{id_periodo_contable}/estado-resultados/acumulado", tags=[TAG_REP],
            dependencies=[Depends(permiso("estado_resultados", R))],
            summary="Acumulado del período (también abierto): ganancias como ingresos y pérdidas como gastos, sin versión")
def acumulado_estado(id_periodo_contable: int, dto: FiltrosEstadoDTO = Depends(), m: M06 = Depends(_m06)) -> dict:
    return m.estado_resultados().acumulado(id_periodo_contable, dto.model_dump())


@router.get("/estados-resultados/{id_estado}", tags=[TAG_REP], dependencies=[Depends(permiso("estado_resultados", R))],
            summary="Detalle de un estado de resultados")
def obtener_estado(id_estado: int, m: M06 = Depends(_m06)) -> dict:
    estado = m.reportes.obtener_estado(id_estado)
    if estado is None:
        raise NotFoundError(code="ESTADO_RESULTADOS_NO_ENCONTRADO", message="El estado de resultados no existe.")
    return estado


@router.post("/periodos/{id_periodo_contable}/estados-resultados", tags=[TAG_REP], status_code=201,
             dependencies=[Depends(permiso("estado_resultados", C))],
             summary="Generar el estado de resultados (filtros opcionales: especie, activo, infraestructura, finca)")
def generar_estado(id_periodo_contable: int, dto: FiltrosEstadoDTO, m: M06 = Depends(_m06),
                   usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.estado_resultados().generar(id_periodo_contable, dto.model_dump(), usuario.id_usuario)


@router.post("/estados-resultados/{id_estado}/aprobacion", tags=[TAG_REP],
             dependencies=[Depends(permiso("estado_resultados", U))], summary="Aprobar el estado de resultados")
def aprobar_estado(id_estado: int, m: M06 = Depends(_m06), usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.estado_resultados().aprobar(id_estado, usuario.id_usuario)


@router.get("/estados-resultados/{id_estado}/descarga", tags=[TAG_REP],
            dependencies=[Depends(permiso("estado_resultados", R))], summary="Descargar el estado aprobado (pdf o excel)")
def descargar_estado(id_estado: int, formato: str = Query("pdf", pattern="^(pdf|excel)$"), m: M06 = Depends(_m06)) -> Response:
    return _descarga(*m.exportar().estado_resultados(id_estado, formato))


@router.get("/periodos/{id_periodo_contable}/revelaciones", tags=[TAG_REP],
            dependencies=[Depends(permiso("revelaciones_nic41", R))], summary="Versiones del informe de revelaciones")
def listar_informes(id_periodo_contable: int, m: M06 = Depends(_m06)) -> list[dict]:
    return m.reportes.listar_informes(id_periodo_contable)


@router.get("/revelaciones/{id_informe}", tags=[TAG_REP], dependencies=[Depends(permiso("revelaciones_nic41", R))],
            summary="Detalle del informe de revelaciones")
def obtener_informe(id_informe: int, m: M06 = Depends(_m06)) -> dict:
    informe = m.reportes.obtener_informe(id_informe)
    if informe is None:
        raise NotFoundError(code="INFORME_NO_ENCONTRADO", message="El informe no existe.")
    return informe


@router.post("/periodos/{id_periodo_contable}/revelaciones", tags=[TAG_REP], status_code=201,
             dependencies=[Depends(permiso("revelaciones_nic41", C))],
             summary="Generar el informe de revelaciones NIC 41 en borrador")
def generar_informe(id_periodo_contable: int, dto: InformeRevelacionesDTO, m: M06 = Depends(_m06),
                    usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    manuales = dto.model_dump(mode="json", exclude={"justificacion_inconsistencias"})
    return m.informe_revelaciones().generar(id_periodo_contable, manuales, dto.justificacion_inconsistencias,
                                            usuario.id_usuario)


@router.post("/revelaciones/{id_informe}/resolucion", tags=[TAG_REP],
             dependencies=[Depends(permiso("revelaciones_nic41", U))], summary="Aprobar o rechazar el borrador")
def resolver_informe(id_informe: int, dto: ResolverInformeDTO, m: M06 = Depends(_m06),
                     usuario: UsuarioActual = Depends(get_current_user)) -> dict:
    return m.informe_revelaciones().resolver(id_informe, dto.aprobar, dto.razon_rechazo, usuario.id_usuario)


@router.get("/revelaciones/{id_informe}/descarga", tags=[TAG_REP], dependencies=[Depends(permiso("revelaciones_nic41", R))],
            summary="Descargar el informe aprobado (pdf o excel)")
def descargar_informe(id_informe: int, formato: str = Query("pdf", pattern="^(pdf|excel)$"), m: M06 = Depends(_m06)) -> Response:
    return _descarga(*m.exportar().informe(id_informe, formato))


# --- Auditoría (RF-94) ---------------------------------------------------------------------------------------

@router.get("/auditoria", tags=["M06 · Auditoría financiera"], dependencies=[Depends(permiso("auditoria_financiera", R))],
            summary="Eventos de auditoría de M06 (técnicos o legibles)")
def consultar_auditoria(tipo_evento: Optional[list[str]] = Query(None),
                        id_periodo_contable: Optional[int] = Query(None, gt=0),
                        id_activo_biologico: Optional[int] = Query(None, gt=0), severidad: Optional[Severidad] = None,
                        id_usuario: Optional[int] = Query(None, gt=0), id_referencia: Optional[int] = Query(None, gt=0),
                        origen_registro: Optional[Literal["REPOSITORIO", "FALLBACK"]] = None,
                        desde: Optional[datetime] = None, hasta: Optional[datetime] = None, pagina: int = Query(1, ge=1),
                        tamano: int = Query(100, ge=1, le=500), formato: str = Query("LEGIBLE", pattern="^(LEGIBLE|TECNICO)$"),
                        orden: Literal["ASC", "DESC"] = "ASC", m: M06 = Depends(_m06)) -> dict:
    filtros = {"tipo_evento": tipo_evento, "id_periodo_contable": id_periodo_contable,
               "id_activo_biologico": id_activo_biologico, "severidad": severidad, "id_usuario": id_usuario,
               "id_referencia": id_referencia, "origen_registro": origen_registro, "desde": desde, "hasta": hasta}
    return m.consultar_auditoria().execute(filtros, pagina, tamano, formato == "LEGIBLE", orden == "DESC")


@router.get("/auditoria/usuarios", tags=["M06 · Auditoría financiera"],
            dependencies=[Depends(permiso("auditoria_financiera", R))],
            summary="Usuarios con eventos en la auditoría del período, para el filtro por usuario")
def usuarios_auditoria(id_periodo_contable: int = Query(..., gt=0), m: M06 = Depends(_m06)) -> list[dict]:
    return m.consultar_auditoria().actores(id_periodo_contable)
