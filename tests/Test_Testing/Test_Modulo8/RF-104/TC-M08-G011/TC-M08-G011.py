# | Fecha      | Nombre           | Que se hizo                                                                        |
# |------------|------------------|------------------------------------------------------------------------------------|
# | 2026-11-20 | Daniela Castillo | M08 RF-104: script del grupo TC-M08-G011 (pytest + sandbox, formato de Excel y PDF) |
"""
TC-M08-G011 - Formato de los archivos Excel y PDF.  RF-104 (CU-02).   Casos: TC-M08-017 a TC-M08-019.

- 017 Excel: hojas 'Resumen Ejecutivo' y 'Datos Detallados' (ficha animal: una hoja por seccion), montos y numeros como NUMBER con
  2 decimales, fechas como DATE (no texto), sin celdas combinadas y primera fila de cada hoja como encabezados.
- 018 PDF: tamano carta, fuente de 10 pt o mas, pie 'Pagina N de M' en todas las paginas, encabezado completo (razon social, NIT, finca,
  periodo/rango y fecha) y sello 'Generado por Sistema de Gestion Pecuaria Multiespecie - Universidad Surcolombiana' en la ultima pagina.
- 019 NIC 41 con exportacion a SIGCON pendiente (periodo 635: 2 facturas listas y ninguna solicitud SIGCON): encabezado y filas dicen
  'Exportacion pendiente'; campo SINIGAN presente en cada activo (CA-20) y firma electronica del Contador en la ultima pagina del PDF.
- No se prueba el limite de 50 MB ni las partes sin ZIP (FA-06): exigen un archivo enorme que no cabe en el run.
- Cada archivo se genera DENTRO del run (sandbox, rollback) y se descarga y abre en memoria; nada queda en el disco.

Requisitos: pip install pytest pytest-html requests openpyxl pdfplumber

Variables (las mismas que pide correr_newman.ps1; si ya las escribiste en esta terminal, se reutilizan):
    QA_SANDBOX_SECRET (o TEST_SANDBOX_SECRET), QA_CONTRASENA_M08_PRODUCTOR, QA_CONTRASENA_M08_CONTADOR, QA_CONTRASENA_M08_INGENIERO
    Opcionales: BASE_URL, QA_CORREO_M08_PRODUCTOR / _CONTADOR / _INGENIERO, QA_ID_FINCA (494), QA_ID_PERIODO_CERRADO (635), QA_ID_ACTIVO_FICHA (2563)

Como correrlo (desde sgpmp-backend):
    python -m pytest "tests/Test_Testing/Test_Modulo8/RF-104/TC-M08-G011/TC-M08-G011.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo8/RF-104/TC-M08-G011/reporte-TC-M08-G011-V1.0.html" --self-contained-html
"""
from __future__ import annotations

import atexit
import datetime as dt
import io
import os
import re
import time
import uuid

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
if "/sigab" in BASE_URL:
    pytest.exit("BASE_URL apunta a MAIN (/sigab): ese ambiente nunca se prueba.", returncode=2)
SECRETO = os.getenv("TEST_SANDBOX_SECRET") or os.getenv("QA_SANDBOX_SECRET", "")
ID_FINCA = int(os.getenv("QA_ID_FINCA", "494"))
ID_PERIODO = int(os.getenv("QA_ID_PERIODO_CERRADO", "635"))
ID_ACTIVO = int(os.getenv("QA_ID_ACTIVO_FICHA", "2563"))
TIMEOUT = 90
LIMITE_RUN = 165
CUENTAS = {
    "productor": (os.getenv("QA_CORREO_M08_PRODUCTOR", "qa.m08.productor@sgpmp-test.com"), "QA_CONTRASENA_M08_PRODUCTOR"),
    "contador": (os.getenv("QA_CORREO_M08_CONTADOR", "qa.m08.contador@sgpmp-test.com"), "QA_CONTRASENA_M08_CONTADOR"),
    "ingeniero": (os.getenv("QA_CORREO_M08_INGENIERO", "qa.m08.ingeniero@sgpmp-test.com"), "QA_CONTRASENA_M08_INGENIERO"),
}
SELLO = "Generado por Sistema de Gestión Pecuaria Multiespecie — Universidad Surcolombiana"
PENDIENTE = "Exportación pendiente"
SIN_SINIGAN = "Sin registro SINIGAN"
HOY = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).date().isoformat()


class Resp:
    def __init__(self, r: requests.Response):
        self.status, self.contenido, self.cabeceras = r.status_code, r.content, r.headers
        try:
            self.data = r.json()
        except ValueError:
            self.data = None

    def __repr__(self) -> str:
        return f"HTTP {self.status} {str(self.contenido[:300])}"


class Entorno:
    """Un run de sandbox (nunca se confirma) y los tokens de las cuentas de QA (login fuera del run)."""

    def __init__(self, roles):
        if not SECRETO:
            pytest.fail("Falta el secreto del sandbox: QA_SANDBOX_SECRET (o TEST_SANDBOX_SECRET).", pytrace=False)
        self.tokens, self.run_id, self.inicio = {}, None, None
        atexit.register(self.cerrar)
        for rol in roles:
            correo, var = CUENTAS[rol]
            clave = os.getenv(var, "")
            if not clave or clave.startswith("<"):
                pytest.fail(f"Falta la contraseña de {rol}: variable {var}.", pytrace=False)
            r = requests.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": correo, "contrasena": clave}, timeout=TIMEOUT)
            if r.status_code != 200:
                pytest.fail(f"PRECONDICION: login de {rol} ({correo}) respondió {r.status_code}", pytrace=False)
            self.tokens[rol] = r.json()["token"]

    def call(self, metodo, ruta, rol=None, json=None) -> Resp:
        if self.run_id is None or (time.time() - self.inicio) > LIMITE_RUN:
            self.nuevo_run()
        h = {"Content-Type": "application/json", "X-Zona-Horaria": "America/Bogota",
             "X-Test-Run-Id": self.run_id, "X-Sandbox-Secret": SECRETO}
        if rol:
            h["Authorization"] = f"Bearer {self.tokens[rol]}"
        return Resp(requests.request(metodo, f"{BASE_URL}{ruta}", headers=h, json=json, timeout=TIMEOUT))

    def nuevo_run(self):
        self.cerrar()
        self.run_id, self.inicio = f"test-pytest-{uuid.uuid4().hex}", time.time()

    def cerrar(self):
        if self.run_id:
            rid, self.run_id = self.run_id, None
            try:
                requests.request("DELETE", f"{BASE_URL}/test-control/runs/{rid}",
                                 headers={"X-Test-Run-Id": rid, "X-Sandbox-Secret": SECRETO}, timeout=TIMEOUT)
            except requests.RequestException:
                pass

    def archivo(self, rol, tipo, formato, filtros) -> bytes:
        """Genera el reporte (201) y descarga su parte 1. Falla con diagnóstico si algo no responde como se espera."""
        g = self.call("POST", "/reportes", rol, {"tipo_reporte": tipo, "formato": formato, "filtros": filtros})
        assert g.status == 201, f"PRECONDICION: generar {tipo} {formato} respondió {g}"
        assert g.data["estado"] == "GENERADO" and g.data["partes"], f"PRECONDICION: {g}"
        d = self.call("GET", f"/reportes/{g.data['id_reporte']}/partes/1/descarga", rol)
        assert d.status == 200, f"PRECONDICION: la descarga respondió {d}"
        assert len(d.contenido) > 500, "PRECONDICION: el archivo llegó vacío"
        return d.contenido


@pytest.fixture(scope="module")
def env():
    e = Entorno(("productor", "contador", "ingeniero"))
    yield e
    e.cerrar()


# --------------------------------------------------------------------------------------------------------------------- Excel
def _libro(datos: bytes):
    openpyxl = pytest.importorskip("openpyxl")
    return openpyxl.load_workbook(io.BytesIO(datos))


def _revisar_excel(wb, con_hojas_estandar: bool):
    """Devuelve la lista de incumplimientos del formato (vacía = cumple) y datos informativos."""
    fallos, info = [], []
    nombres = wb.sheetnames
    if con_hojas_estandar:
        for n in ("Resumen Ejecutivo", "Datos Detallados"):
            if n not in nombres:
                fallos.append(f"falta la hoja '{n}' (hojas: {nombres})")
    elif "Resumen Ejecutivo" not in nombres:
        fallos.append(f"falta la hoja 'Resumen Ejecutivo' (hojas: {nombres})")
    for ws in wb.worksheets:
        if ws.merged_cells.ranges:
            fallos.append(f"hoja '{ws.title}': hay celdas combinadas {[str(r) for r in ws.merged_cells.ranges]}")
        fila1 = [c.value for c in ws[1]]
        if not fila1 or fila1[0] in (None, ""):
            fallos.append(f"hoja '{ws.title}': la primera fila no es de encabezados")
        elif ws.title == "Datos Detallados" and any(v in (None, "") for v in fila1):
            fallos.append(f"hoja '{ws.title}': encabezados incompletos en la primera fila {fila1}")
        for fila in ws.iter_rows(min_row=2):
            for c in fila:
                v = c.value
                if isinstance(v, bool):
                    continue
                if isinstance(v, (int, float)):
                    es_entero = isinstance(v, int) or float(v).is_integer()
                    if not (re.search(r"0\.00\b", c.number_format or "") or (es_entero and (c.number_format or "") in ("0", "General"))):
                        fallos.append(f"{ws.title}!{c.coordinate} = {v!r} con formato '{c.number_format}': no es NUMBER con 2 decimales")
                    if abs(float(v) * 100 - round(float(v) * 100)) > 1e-6:
                        info.append(f"{ws.title}!{c.coordinate} = {v!r} guarda más de 2 decimales")
                elif isinstance(v, (dt.datetime, dt.date)):
                    if not re.search(r"y|d|m", (c.number_format or "").lower()) or (c.number_format or "") == "General":
                        fallos.append(f"{ws.title}!{c.coordinate}: fecha sin formato de fecha ('{c.number_format}')")
                elif isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$", v):
                    fallos.append(f"{ws.title}!{c.coordinate} = '{v}': fecha guardada como TEXTO")
                elif isinstance(v, str) and re.match(r"^\$? ?[\d.]+,\d{2}$", v):
                    fallos.append(f"{ws.title}!{c.coordinate} = '{v}': monto guardado como TEXTO")
    return fallos, info


def _hay_numeros(wb) -> int:
    return sum(1 for ws in wb.worksheets for fila in ws.iter_rows(min_row=2) for c in fila
               if isinstance(c.value, (int, float)) and not isinstance(c.value, bool))


def test_TC_M08_017a_excel_inventario_hojas_y_formato(env):
    wb = _libro(env.archivo("productor", "REPORTE_INVENTARIO_BIOLOGICO", "EXCEL",
                            {"fecha_inicio": "2026-01-01", "fecha_fin": HOY, "finca_id": ID_FINCA}))
    fallos, info = _revisar_excel(wb, True)
    print(f"017a hojas: {wb.sheetnames}; celdas numéricas: {_hay_numeros(wb)}; {info[:5]}")
    assert _hay_numeros(wb) > 0, "PRECONDICION: el Excel no trae valores numéricos que revisar"
    assert not fallos, "Formato Excel (inventario biológico): " + " | ".join(fallos[:12])


def test_TC_M08_017b_excel_nic41_montos_con_dos_decimales(env):
    wb = _libro(env.archivo("contador", "REPORTE_VALORACION_NIC41", "EXCEL", {"periodo_contable": ID_PERIODO}))
    fallos, info = _revisar_excel(wb, True)
    print(f"017b hojas: {wb.sheetnames}; celdas numéricas: {_hay_numeros(wb)}; {info[:5]}")
    assert _hay_numeros(wb) > 0, "PRECONDICION: el Excel no trae valores numéricos que revisar"
    assert not fallos, "Formato Excel (NIC 41): " + " | ".join(fallos[:12])


def test_TC_M08_017c_excel_ficha_animal_una_hoja_por_seccion(env):
    wb = _libro(env.archivo("productor", "REPORTE_FICHA_ANIMAL", "EXCEL", {"activo_biologico_id": ID_ACTIVO}))
    fallos, info = _revisar_excel(wb, False)
    print(f"017c hojas: {wb.sheetnames}; {info[:5]}")
    esperadas = ("Identificación", "Historial productivo", "Historial sanitario", "Suministros aplicados",
                 "Valoración financiera por período cerrado", "Predicciones sanitarias activas")
    for n in esperadas:
        if not any(h.startswith(n[:28]) for h in wb.sheetnames):
            fallos.append(f"falta la hoja de la sección '{n}' (hojas: {wb.sheetnames})")
    assert not fallos, "Formato Excel (ficha animal): " + " | ".join(fallos[:12])


# --------------------------------------------------------------------------------------------------------------------- PDF
def _pdf(datos: bytes):
    try:
        import pdfplumber
    except ImportError:
        pytest.fail("PRECONDICION: falta pdfplumber (pip install pdfplumber)", pytrace=False)
    return pdfplumber.open(io.BytesIO(datos))


def _revisar_pdf(pdf, con_firma: bool):
    fallos = []
    n = len(pdf.pages)
    for i, p in enumerate(pdf.pages, start=1):
        a, b = round(p.width), round(p.height)
        if sorted((a, b)) != [612, 792]:
            fallos.append(f"página {i}: tamaño {a}x{b} pt (carta es 612x792)")
        chicas = sorted({round(c["size"], 1) for c in p.chars if c["size"] < 9.95})
        if chicas:
            fallos.append(f"página {i}: fuentes menores de 10 pt {chicas}")
        texto = p.extract_text() or ""
        if f"Página {i} de {n}" not in texto:
            fallos.append(f"página {i}: falta el pie 'Página {i} de {n}'")
    ultima = pdf.pages[-1].extract_text() or ""
    if SELLO not in " ".join(ultima.split()):
        fallos.append("la última página no trae el sello 'Generado por Sistema de Gestión Pecuaria Multiespecie — Universidad Surcolombiana'")
    if con_firma and "Firmado electrónicamente por" not in ultima:
        fallos.append("la última página no trae la firma electrónica del Contador")
    return fallos, n


def test_TC_M08_018a_pdf_varias_paginas_carta_fuente_y_pie(env):
    """Telemetría de 999 lecturas (sensor 1327): varias páginas."""
    pdf = _pdf(env.archivo("ingeniero", "REPORTE_TELEMETRIA", "PDF", {
        "fecha_inicio": "2026-10-18", "fecha_fin": "2026-10-26", "infraestructura_id": 1468, "sensor_id": 1327}))
    fallos, n = _revisar_pdf(pdf, False)
    print(f"018a páginas: {n}")
    assert n > 1, f"PRECONDICION: el PDF de 999 lecturas debía tener varias páginas y tiene {n}"
    assert not fallos, "Formato PDF (telemetría): " + " | ".join(fallos[:12])


def test_TC_M08_018b_pdf_encabezado_completo(env):
    pdf = _pdf(env.archivo("productor", "REPORTE_INVENTARIO_BIOLOGICO", "PDF",
                           {"fecha_inicio": "2026-01-01", "fecha_fin": HOY, "finca_id": ID_FINCA}))
    primera = pdf.pages[0].extract_text() or ""
    faltan = [k for k in ("Razón social", "NIT", "Finca", "Rango de fechas", "Fecha de generación") if k not in primera]
    fallos, n = _revisar_pdf(pdf, False)
    assert not faltan, f"el encabezado de la primera página no trae: {faltan}"
    assert "901777548" in primera.replace(".", "").replace("-", " ").replace(" ", ""), "el NIT 901777548 no aparece en el encabezado"
    assert not fallos, "Formato PDF (inventario): " + " | ".join(fallos[:12])


# --------------------------------------------------------------------------------------------------------------------- NIC 41
def test_TC_M08_019a_nic41_pdf_exportacion_pendiente_y_firma(env):
    pdf = _pdf(env.archivo("contador", "REPORTE_VALORACION_NIC41", "PDF", {"periodo_contable": ID_PERIODO}))
    texto = "\n".join((p.extract_text() or "") for p in pdf.pages)
    fallos, n = _revisar_pdf(pdf, True)
    assert PENDIENTE in texto, "el PDF no dice 'Exportación pendiente' (periodo cerrado sin exportación a SIGCON)"
    assert "Exportación contable" in texto, "el encabezado no trae el campo 'Exportación contable'"
    assert "Identificación SINIGAN" in texto, "falta la columna 'Identificación SINIGAN' (CA-20)"
    assert not fallos, "Formato PDF (NIC 41): " + " | ".join(fallos[:12])


def test_TC_M08_019b_nic41_excel_exportacion_pendiente_y_sinigan(env):
    wb = _libro(env.archivo("contador", "REPORTE_VALORACION_NIC41", "EXCEL", {"periodo_contable": ID_PERIODO}))
    assert "Datos Detallados" in wb.sheetnames, f"PRECONDICION: hojas {wb.sheetnames}"
    ws = wb["Datos Detallados"]
    cab = [c.value for c in ws[1]]
    for col in ("Identificación SINIGAN", "Exportación contable", "Estado de la exportación"):
        assert col in cab, f"falta la columna '{col}' (columnas: {cab})"
    filas = [[c.value for c in f] for f in ws.iter_rows(min_row=2) if f[0].value not in (None, "")]
    assert filas, "PRECONDICION: el NIC 41 del periodo 635 no trae activos"
    i_exp, i_est, i_sin = cab.index("Exportación contable"), cab.index("Estado de la exportación"), cab.index("Identificación SINIGAN")
    mal = [f[0] for f in filas if f[i_exp] != PENDIENTE or f[i_est] != "Pendiente"]
    assert not mal, f"activos sin la marca '{PENDIENTE}': {mal}"
    sin = [f[0] for f in filas if f[i_sin] in (None, "")]
    assert not sin, f"activos sin valor en 'Identificación SINIGAN' (debe traer el SINIGAN o '{SIN_SINIGAN}'): {sin}"
    resumen = " ".join(str(c.value) for f in wb["Resumen Ejecutivo"].iter_rows() for c in f if c.value)
    assert PENDIENTE in resumen, "la hoja 'Resumen Ejecutivo' no dice 'Exportación pendiente'"
    print("019b SINIGAN por activo:", {f[0]: f[i_sin] for f in filas})
