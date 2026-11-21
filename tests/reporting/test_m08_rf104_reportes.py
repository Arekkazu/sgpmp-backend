# | Fecha      | Nombre   | Que se hizo                                                                     |
# |------------|----------|---------------------------------------------------------------------------------|
# | 2026-11-18 | Arekkazu | M08 RF-104: filtros, permisos, períodos, armado, Excel/PDF, partes y ciclo de vida |
# | 2026-11-19 | Arekkazu | M08 RF-104: plantillas V1.1, indicadores, parámetros y encabezado del animal |
"""RF-104 — reportes: validación, ciclo de la solicitud, contenido de los reportes, archivos y casos de uso.

Sin BD: la fuente, el repositorio y los avisos son dobles en memoria. Las consultas SQL tienen su prueba de
integración (``tests/integration/test_m08_rf104_rf107_integration.py``).
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from src.reporting.application.use_cases.reportes import generacion
from src.reporting.application.use_cases.reportes.armadores import (
    ARMADORES,
    EXPORTACION_PENDIENTE,
    SIN_CAUSA,
    SIN_SINIGAN,
    Contexto,
    _fincas_filtro,
)
from src.reporting.application.use_cases.reportes.descargar_reporte_use_case import DescargarReporteUseCase
from src.reporting.application.use_cases.reportes.generacion import Solicitante, partir_en_archivos, preparar
from src.reporting.application.use_cases.reportes.procesar_reportes_pendientes_use_case import (
    ProcesarReportesPendientesUseCase,
)
from src.reporting.application.use_cases.reportes.solicitar_reporte_use_case import SolicitarReporteUseCase
from src.reporting.domain.reportes.catalogo import CATALOGO, LIMITE_SINCRONO, validar_filtros
from src.reporting.domain.reportes.contenido import FECHA, MONEDA, Columna, ContenidoReporte, Tabla
from src.reporting.domain.reportes.solicitud import (
    CANCELADO,
    EN_PROCESO,
    EXCEL,
    FALLIDO,
    GENERADO,
    PDF,
    ArchivoReporte,
    SolicitudReporte,
    sha256,
)
from src.reporting.infrastructure.adapters.renderizador_reportes import RenderizadorReportes, texto_celda
from src.shared.errors import (
    AuthorizationError,
    BusinessRuleError,
    FlowError,
    GoneError,
    NotFoundError,
    ValidationError,
)

HOY = date(2026, 11, 18)
AHORA = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
TODOS = set(CATALOGO)
PERIODO_CERRADO = {"id_periodo_contable": 7, "fecha_inicio": date(2026, 10, 1), "fecha_fin": date(2026, 10, 31),
                   "estado": "CERRADO", "nit": "900123456", "accesible": True}
PERIODO_ABIERTO = {**PERIODO_CERRADO, "id_periodo_contable": 8, "fecha_inicio": date(2026, 11, 1),
                   "fecha_fin": date(2026, 11, 30), "estado": "ABIERTO"}


class FuenteFalsa:
    """Fuente en memoria: cada método devuelve lo que la prueba deje en ``datos``."""

    def __init__(self, **datos: Any) -> None:
        self.datos = datos
        self.llamadas: list[str] = []

    def __getattr__(self, nombre: str):
        def metodo(*args, **kwargs):
            self.llamadas.append(nombre)
            valor = self.datos.get(nombre, [])
            return valor(*args, **kwargs) if callable(valor) else valor
        return metodo

    def ubicar(self, tipo, id_referencia):
        return self.datos.get("ubicaciones", {}).get((tipo, id_referencia))

    def periodo(self, id_periodo):
        return {p["id_periodo_contable"]: p for p in self.datos.get("periodos", [])}.get(id_periodo)

    def fincas(self, fincas):
        return [{"id_finca": 1, "nombre": "La Esperanza", "razon_social": "Agro SAS", "nit": "900123456", "dv": "7"}]

    def fincas_de_titular(self, nit, fincas):
        return [1]

    def ruta_logo(self, id_finca):
        return None

    def nombres_usuarios(self, ids):
        return {i: f"Usuario {i}" for i in ids}


def _ctx(tipo: str, fuente: FuenteFalsa, filtros: Optional[dict] = None, **extra) -> Contexto:
    return Contexto(fuente=fuente, tipo=tipo, filtros=filtros or {"fecha_inicio": date(2026, 11, 1), "fecha_fin": HOY},
                    fincas=[1], hoy=HOY, generado=AHORA, **extra)


# --- Catálogo y filtros ------------------------------------------------------------------------

def test_catalogo_tiene_los_18_reportes_con_su_recurso():
    assert len(CATALOGO) == 18 and set(ARMADORES) == set(CATALOGO)
    assert CATALOGO["REPORTE_EJECUTIVO_CONSOLIDADO"].recurso == "reporte_ejecutivo_consolidado"


def test_filtro_obligatorio_faltante_responde_400_con_el_campo():
    with pytest.raises(ValidationError) as exc:
        validar_filtros(CATALOGO["REPORTE_INVENTARIO_BIOLOGICO"], {"fecha_inicio": "2026-11-01"}, HOY)
    assert exc.value.field == "filtros.fecha_fin"
    assert "Fecha de fin" in exc.value.message


@pytest.mark.parametrize("crudos", [
    {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-10", "estado_activo": "PERDIDO"},
    {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-10", "otro": 1},
    {"fecha_inicio": "2026-11-11", "fecha_fin": "2026-11-10"},
    {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-12-10"},
    {"fecha_inicio": "1/11/2026", "fecha_fin": "2026-11-10"},
    {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-10", "especie_id": True},
])
def test_filtros_invalidos_responden_400(crudos):
    with pytest.raises(ValidationError):
        validar_filtros(CATALOGO["REPORTE_INVENTARIO_BIOLOGICO"], crudos, HOY)


def test_todos_no_filtra_y_fecha_de_corte_toma_hoy():
    filtros = validar_filtros(CATALOGO["REPORTE_ESTADO_DISPOSITIVOS"], {"estado_dispositivo": "TODOS"}, HOY)
    assert filtros == {"fecha_corte": HOY}


# --- Solicitud ---------------------------------------------------------------------------------

def _generada(id_usuario: int = 5) -> SolicitudReporte:
    s = SolicitudReporte(id_usuario=id_usuario, tipo_reporte="REPORTE_INVENTARIO_BIOLOGICO", formato=PDF,
                         id_solicitud_reporte=uuid4())
    parte = ArchivoReporte(1, "a.pdf", "application/pdf", b"abc", 3, sha256(b"abc"))
    s.registrar_generacion([parte], 1, AHORA, AHORA)
    return s


def test_solo_el_dueno_descarga_y_vence_a_las_48_horas():
    s = _generada()
    s.exigir_descargable(5, AHORA + timedelta(hours=47))
    with pytest.raises(AuthorizationError):
        s.exigir_descargable(6, AHORA)
    with pytest.raises(GoneError):
        s.exigir_descargable(5, AHORA + timedelta(hours=48))


def test_en_proceso_no_se_descarga_y_falla_tras_tres_intentos():
    s = SolicitudReporte(id_usuario=5, tipo_reporte="REPORTE_TELEMETRIA", formato=EXCEL)
    s.encolar(AHORA)
    with pytest.raises(FlowError):
        s.exigir_descargable(5, AHORA)
    assert s.registrar_intento_fallido(AHORA) is False
    assert s.fecha_proximo_intento == AHORA + timedelta(seconds=30)
    assert s.registrar_intento_fallido(AHORA) is False
    assert s.registrar_intento_fallido(AHORA) is True and s.estado == FALLIDO


def test_cancelar_solo_en_proceso_y_solo_el_dueno():
    s = SolicitudReporte(id_usuario=5, tipo_reporte="REPORTE_TELEMETRIA", formato=EXCEL)
    with pytest.raises(AuthorizationError):
        s.cancelar(9)
    s.cancelar(5)
    assert s.estado == CANCELADO
    with pytest.raises(FlowError):
        s.cancelar(5)


def test_archivo_integro_segun_checksum():
    assert ArchivoReporte(1, "a", "x", b"abc", 3, sha256(b"abc")).integro()
    assert not ArchivoReporte(1, "a", "x", b"abd", 3, sha256(b"abc")).integro()


# --- Validación de permisos, referencias y períodos --------------------------------------------

def _solicitante(permitidos=TODOS, fincas=(1,)) -> Solicitante:
    return Solicitante(5, "Ana Pérez", set(permitidos), list(fincas) if fincas is not None else None, "UTC")


def test_tipo_sin_permiso_responde_403():
    with pytest.raises(AuthorizationError):
        preparar(FuenteFalsa(), "REPORTE_VALORACION_NIC41", {"periodo_contable": 7},
                 _solicitante({"REPORTE_INVENTARIO_BIOLOGICO"}))


def test_periodo_abierto_responde_422_y_comparacion_posterior_tambien():
    fuente = FuenteFalsa(periodos=[PERIODO_CERRADO, PERIODO_ABIERTO])
    with pytest.raises(BusinessRuleError) as exc:
        preparar(fuente, "REPORTE_VALORACION_NIC41", {"periodo_contable": 8}, _solicitante())
    assert exc.value.code == "PERIODO_NO_CERRADO" and "8" not in exc.value.message
    nuevo = {**PERIODO_CERRADO, "id_periodo_contable": 9, "fecha_inicio": date(2026, 9, 1),
             "fecha_fin": date(2026, 9, 30)}
    fuente = FuenteFalsa(periodos=[PERIODO_CERRADO, nuevo])
    with pytest.raises(BusinessRuleError, match="anterior al período base"):
        preparar(fuente, "REPORTE_VARIACION_PERIODOS",
                 {"periodo_contable_base": 9, "periodo_contable_comparacion": 7}, _solicitante())


def test_ficha_de_otra_finca_es_403_y_la_inexistente_404():
    fuente = FuenteFalsa(ubicaciones={("activo", 10): {"id": 10, "id_finca": 2}})
    with pytest.raises(AuthorizationError):
        preparar(fuente, "REPORTE_FICHA_ANIMAL", {"activo_biologico_id": 10}, _solicitante())
    with pytest.raises(NotFoundError):
        preparar(fuente, "REPORTE_FICHA_ANIMAL", {"activo_biologico_id": 11}, _solicitante())


# --- Armado de reportes ------------------------------------------------------------------------

_INVENTARIO = [
    {"id_activo_biologico": 1, "identificador": "BOV-1", "especie": "Bovino", "raza": "Brahman", "sinigan": None,
     "estado": "ACTIVO", "tipo_baja": None, "fecha_ingreso": date(2026, 1, 1), "tipo_activo": "INDIVIDUAL",
     "peso_kg": Decimal("320"), "etapa": "Ceba", "cantidad": 1, "metodo": "VALOR_RAZONABLE",
     "valor": Decimal("1639000"), "finca": "La Esperanza", "id_finca": 1},
    {"id_activo_biologico": 2, "identificador": "LOTE-2", "especie": "Aves", "raza": None, "sinigan": "CO-9",
     "estado": "BAJA", "tipo_baja": "venta", "fecha_ingreso": date(2026, 2, 1), "tipo_activo": "POBLACIONAL",
     "peso_kg": None, "etapa": None, "cantidad": 40, "metodo": None, "valor": None, "finca": "La Esperanza",
     "id_finca": 1},
]


def test_inventario_marca_sin_sinigan_y_advierte_la_trazabilidad():
    c = ARMADORES["REPORTE_INVENTARIO_BIOLOGICO"](_ctx("REPORTE_INVENTARIO_BIOLOGICO", FuenteFalsa(inventario=_INVENTARIO)))
    filas = c.detalle.filas
    assert filas[0]["sinigan"] == SIN_SINIGAN and filas[1]["sinigan"] == "CO-9"
    assert filas[1]["estado"] == "Vendido" and filas[1]["lote"] == "LOTE-2" and filas[0]["lote"] == "No aplica"
    assert c.advertencias and "1 activo no tiene" in c.advertencias[0]
    assert ("NIT", "900123456-7") in c.encabezado


def test_bajas_sin_causa_de_muerte_dicen_causa_no_registrada():
    salida = [{"id_activo_biologico": 2, "identificador": "LOTE-2", "sinigan": None, "especie": "Aves",
               "tipo": "MUERTE", "fecha": AHORA, "motivo": None, "valor_venta": None, "destino": None,
               "cantidad": 10, "finca": "La Esperanza", "valor_referencia": Decimal("500")}]
    c = ARMADORES["REPORTE_BAJAS_Y_SALIDAS"](_ctx("REPORTE_BAJAS_Y_SALIDAS", FuenteFalsa(salidas=salida)))
    fila = c.detalle.filas[0]
    assert fila["motivo"] == SIN_CAUSA and fila["origen_valor"] == "Valor razonable del último cierre"
    assert any("trazabilidad" in a for a in c.advertencias)
    assert any("SINIGAN" in a for a in c.advertencias)


def test_nic41_sin_exportacion_dice_exportacion_pendiente_y_lleva_firma():
    valoracion = [{"id_activo_biologico": 1, "identificador": "BOV-1", "sinigan": "CO-1", "especie": "Bovino",
                   "metodo": "VALOR_RAZONABLE", "valor_razonable": Decimal("1639000"), "costo_atribuido": None,
                   "variacion": Decimal("189000"), "finca": "La Esperanza"}]
    ctx = _ctx("REPORTE_VALORACION_NIC41", FuenteFalsa(valoracion_periodo=valoracion, exportaciones=[]),
               {"periodo_contable": 7}, periodos={"periodo_contable": PERIODO_CERRADO}, nombre_usuario="Ana Pérez")
    c = ARMADORES["REPORTE_VALORACION_NIC41"](ctx)
    assert ("Exportación contable", EXPORTACION_PENDIENTE) in c.encabezado
    assert c.detalle.filas[0]["id_exportacion"] == EXPORTACION_PENDIENTE and c.firma == "Ana Pérez"


def test_vacunacion_incluye_los_animales_en_periodo_de_retiro():
    retiros = [{"identificador": "BOV-1", "especie": "Bovino", "medicamento": "Ivermectina",
                "fecha_aplicacion": date(2026, 11, 15), "fecha_fin_retiro": date(2026, 12, 13), "finca": "La Esperanza"}]
    c = ARMADORES["REPORTE_VACUNACION_MEDICAMENTOS"](_ctx("REPORTE_VACUNACION_MEDICAMENTOS",
                                                          FuenteFalsa(retiros_vigentes=retiros)))
    assert c.finales[0].filas[0]["animal"] == "BOV-1" and "No sacrificar" in c.finales[0].nota


def test_dispositivos_sin_datos_hace_mas_de_24_horas_son_prioritarios():
    dispositivos = [
        {"id_dispositivo_iot": 1, "serial": "SN-1", "tipo": "Sensor", "area": "Galpón", "finca": "La Esperanza",
         "estado": "SIN_SEÑAL", "ultimo_dato": AHORA - timedelta(hours=30), "instalacion": AHORA,
         "mantenimiento": None, "version_firmware": None, "desconexiones": 2},
        {"id_dispositivo_iot": 2, "serial": "SN-2", "tipo": "Sensor", "area": "Galpón", "finca": "La Esperanza",
         "estado": "ACTIVO", "ultimo_dato": AHORA - timedelta(minutes=5), "instalacion": AHORA,
         "mantenimiento": None, "version_firmware": "1.2.0", "desconexiones": 0},
    ]
    c = ARMADORES["REPORTE_ESTADO_DISPOSITIVOS"](_ctx("REPORTE_ESTADO_DISPOSITIVOS", FuenteFalsa(dispositivos=dispositivos),
                                                      {"fecha_corte": HOY}))
    prioritarios = c.resumen[1].filas
    assert [p["serial"] for p in prioritarios] == ["SN-1"]


def test_ejecutivo_solo_usa_consultas_de_totales():
    fuente = FuenteFalsa(ultimo_periodo_cerrado=PERIODO_CERRADO,
                         valor_portafolio=[{"finca": "La Esperanza", "valor": Decimal("1000")}])
    c = ARMADORES["REPORTE_EJECUTIVO_CONSOLIDADO"](_ctx("REPORTE_EJECUTIVO_CONSOLIDADO", fuente,
                                                        {"periodo_contable": 8},
                                                        periodos={"periodo_contable": PERIODO_ABIERTO}))
    assert c.detalle is None and len(c.secciones) == 5
    individuales = {"inventario", "valoracion_periodo", "eventos_sanitarios", "predicciones_activas", "exportaciones"}
    assert not (individuales - {"exportaciones"}) & set(fuente.llamadas)


# --- Archivos ----------------------------------------------------------------------------------

def _contenido(filas: int = 3) -> ContenidoReporte:
    return ContenidoReporte(
        titulo="Prueba", encabezado=[("Finca", "La Esperanza")],
        resumen=[Tabla("Total", [Columna("c", "Concepto"), Columna("v", "Valor (COP)", MONEDA)],
                       [{"c": "Total", "v": Decimal("1639000.5")}])],
        detalle=Tabla("Detalle", [Columna("f", "Fecha", FECHA), Columna("v", "Valor (COP)", MONEDA),
                                  Columna("x", "Texto")],
                      [{"f": date(2026, 11, i + 1), "v": Decimal("10.456"), "x": None} for i in range(filas)]))


def test_excel_guarda_montos_como_numero_y_fechas_como_fecha():
    libro = load_workbook(io.BytesIO(RenderizadorReportes().renderizar(_contenido(), EXCEL, None)))
    assert libro.sheetnames == ["Resumen Ejecutivo", "Datos Detallados"]
    hoja = libro["Datos Detallados"]
    assert [c.value for c in hoja[1]] == ["Fecha", "Valor (COP)", "Texto"]
    assert hoja["A2"].is_date and hoja["A2"].number_format == "yyyy-mm-dd"
    assert hoja["B2"].value == 10.46 and hoja["B2"].number_format == "#,##0.00"
    assert hoja["C2"].value == "Sin dato"
    assert not any(h.merged_cells.ranges for h in libro.worksheets)


def test_pdf_es_valido_y_formatea_como_en_colombia():
    pdf = RenderizadorReportes().renderizar(_contenido(), PDF, None)
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
    assert texto_celda(Decimal("1639000"), MONEDA) == "$ 1.639.000,00"
    assert texto_celda(date(2026, 11, 18), FECHA) == "18/11/2026"


def test_plantilla_v11_parametros_indicadores_y_finca_del_animal():
    """M8-08/M8-12/M8-13: el encabezado lleva la finca del animal, los filtros se leen con nombres, el Excel guarda
    la fecha de generación como fecha y las cifras del PDF no se parten."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from src.reporting.infrastructure.adapters import renderizador_reportes as rr

    fuente = FuenteFalsa(ubicaciones={("activo", 2): {"id": 2, "id_finca": 3}},
                         nombre_referencia=lambda tipo, id_ref: "BOV-002")
    s = _solicitante(fincas=(1, 3))
    s.rol = "Veterinario"
    p = preparar(fuente, "REPORTE_HISTORICO_SANITARIO", {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-10",
                                                          "activo_biologico_id": 2}, s, AHORA)
    assert ("Animal o lote", "BOV-002") in p.contenido.parametros and ("Especie", "Todas") in p.contenido.parametros
    assert p.contenido.generado_por == "Ana Pérez (Veterinario)"
    assert [i.etiqueta for i in p.contenido.indicadores] == ["Total de eventos", "Tasa de resolución clínica",
                                                             "Activos atendidos"]
    assert _fincas_filtro(_ctx("REPORTE_HISTORICO_SANITARIO", fuente, {"activo_biologico_id": 2})) == [3]

    libro = load_workbook(io.BytesIO(RenderizadorReportes().renderizar(p.contenido, EXCEL, None)))
    filas = {f[0].value: f[1] for f in libro["Resumen Ejecutivo"].iter_rows(min_row=2) if f[0].value}
    assert filas["Fecha de generación"].is_date and filas["Animal o lote"].value == "BOV-002"

    tabla = Tabla("x", [Columna(f"c{i}", f"Columna {i}", MONEDA) for i in range(7)] + [Columna("t", "Identificación")],
                  [{**{f"c{i}": Decimal("2809848.5") for i in range(7)}, "t": "QA-M06-G52-SANITARIO"}])
    anchos = rr._anchos_pdf(tabla, 720)
    cifra = stringWidth(rr._texto_pdf(Decimal("2809848.5"), MONEDA), "Helvetica", 10)
    assert all(a - 2 * rr._PADDING >= cifra for a in anchos[:7]) and abs(sum(anchos) - 720) < 0.01


class RenderizadorFalso(RenderizadorReportes):
    def renderizar(self, contenido, formato, ruta_logo):
        return b"x" * (len(contenido.detalle.filas) * 10 if contenido.detalle else 10)


def test_reporte_de_mas_de_50_mb_sale_en_partes_sin_zip(monkeypatch):
    monkeypatch.setattr(generacion, "LIMITE_PARTE", 25)
    partes = partir_en_archivos(_contenido(filas=6), PDF, RenderizadorFalso(), None, AHORA)
    assert len(partes) > 1 and all(p.tamano_bytes <= 25 for p in partes)
    assert partes[0].nombre_archivo.endswith(f"_parte_1_de_{len(partes)}.pdf")
    assert all(p.integro() for p in partes)


# --- Casos de uso ------------------------------------------------------------------------------

class RepoFalso:
    def __init__(self) -> None:
        self.solicitudes: dict = {}
        self.archivos: dict = {}

    def guardar(self, s):
        self.solicitudes[s.id_solicitud_reporte] = s
        return s

    def guardar_archivos(self, id_s, partes):
        self.archivos[id_s] = partes

    def obtener(self, id_s, bloquear=False):
        return self.solicitudes.get(id_s)

    def obtener_archivo(self, id_s, n):
        return next((p for p in self.archivos.get(id_s, []) if p.numero_parte == n), None)

    def tomar_pendientes(self, ahora, limite):
        return [s for s in self.solicitudes.values() if s.estado == EN_PROCESO][:limite]


class Db:
    def __init__(self) -> None:
        self.commits = self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class Avisos:
    def __init__(self) -> None:
        self.registros: list = []

    def registrar(self, solicitud, titulo, detalle, notificar):
        self.registros.append((solicitud.estado, notificar, detalle))


def _abrir(fuente):
    @contextmanager
    def abrir(id_usuario, zona):
        yield fuente
    return abrir


def _inventario(n: int) -> list[dict]:
    return [{**_INVENTARIO[0], "id_activo_biologico": i, "identificador": f"BOV-{i}"} for i in range(n)]


def test_hasta_mil_registros_se_genera_al_momento_y_se_audita():
    repo, avisos, db = RepoFalso(), Avisos(), Db()
    s = SolicitarReporteUseCase(db, repo, _abrir(FuenteFalsa(inventario=_inventario(3))), RenderizadorReportes(),
                                avisos).execute("REPORTE_INVENTARIO_BIOLOGICO", PDF,
                                                {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-18"},
                                                _solicitante(), AHORA)
    assert s.estado == GENERADO and repo.archivos[s.id_solicitud_reporte][0].integro()
    estado, notificar, detalle = avisos.registros[0]
    assert (estado, notificar) == (GENERADO, False) and detalle["checksum"] == s.checksum_sha256
    assert detalle["filtros_aplicados"] == {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-18"}


def test_mas_de_mil_registros_queda_en_proceso_sin_archivo():
    repo = RepoFalso()
    s = SolicitarReporteUseCase(Db(), repo, _abrir(FuenteFalsa(inventario=_inventario(LIMITE_SINCRONO + 1))),
                                RenderizadorReportes(), Avisos()).execute(
        "REPORTE_INVENTARIO_BIOLOGICO", EXCEL, {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-18"},
        _solicitante(), AHORA)
    assert s.estado == EN_PROCESO and s.id_solicitud_reporte not in repo.archivos


def test_sin_datos_responde_422():
    with pytest.raises(BusinessRuleError) as exc:
        SolicitarReporteUseCase(Db(), RepoFalso(), _abrir(FuenteFalsa()), RenderizadorReportes(), Avisos()).execute(
            "REPORTE_INVENTARIO_BIOLOGICO", PDF, {"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-18"},
            _solicitante(), AHORA)
    assert exc.value.code == "SIN_DATOS"


class FuenteRota(FuenteFalsa):
    def inventario(self, **_):
        raise RuntimeError("caída de la BD")


def _pendiente(repo: RepoFalso) -> SolicitudReporte:
    s = SolicitudReporte(id_usuario=5, tipo_reporte="REPORTE_INVENTARIO_BIOLOGICO", formato=PDF,
                         filtros={"fecha_inicio": "2026-11-01", "fecha_fin": "2026-11-18"}, id_solicitud_reporte=uuid4())
    s.encolar(AHORA)
    return repo.guardar(s)


def test_segundo_plano_reintenta_dos_veces_y_avisa_el_fallo():
    repo, avisos = RepoFalso(), Avisos()
    s = _pendiente(repo)
    caso = ProcesarReportesPendientesUseCase(Db(), repo, _abrir(FuenteRota()), RenderizadorReportes(), avisos,
                                             lambda *_: _solicitante())
    for _ in range(3):
        caso.execute(AHORA, maximo=1)
    assert s.estado == FALLIDO and s.intentos == 3
    assert avisos.registros == [(FALLIDO, True, avisos.registros[0][2])]


def test_segundo_plano_genera_y_avisa_listo():
    repo, avisos = RepoFalso(), Avisos()
    s = _pendiente(repo)
    ProcesarReportesPendientesUseCase(Db(), repo, _abrir(FuenteFalsa(inventario=_inventario(2))),
                                      RenderizadorReportes(), avisos, lambda *_: _solicitante()).execute(AHORA)
    assert s.estado == GENERADO and avisos.registros[0][:2] == (GENERADO, True)


def test_si_el_usuario_perdio_el_permiso_falla_sin_reintentos():
    repo, avisos = RepoFalso(), Avisos()
    s = _pendiente(repo)
    ProcesarReportesPendientesUseCase(Db(), repo, _abrir(FuenteFalsa(inventario=_inventario(2))),
                                      RenderizadorReportes(), avisos, lambda *_: _solicitante(set())).execute(AHORA)
    assert s.estado == FALLIDO and s.intentos == 0 and "permiso" in s.mensaje_error


def test_descarga_con_checksum_alterado_marca_fallido_y_avisa():
    repo, avisos = RepoFalso(), Avisos()
    s = repo.guardar(_generada())
    repo.guardar_archivos(s.id_solicitud_reporte, [ArchivoReporte(1, "a.pdf", "application/pdf", b"zzz", 3,
                                                                  sha256(b"abc"))])
    with pytest.raises(BusinessRuleError):
        DescargarReporteUseCase(Db(), repo, avisos).execute(s.id_solicitud_reporte, 1, 5, AHORA)
    assert s.estado == FALLIDO and avisos.registros[0][:2] == (FALLIDO, True)
