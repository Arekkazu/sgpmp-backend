# -*- coding: utf-8 -*-
"""Biblioteca común de los scripts TC-M06-GXX (Módulo 6, RF-82 a RF-85) con pytest.

Reglas de QA que aplica (sandbox transaccional):
- Cada archivo TC-M06-GXX abre UN run (X-Test-Run-Id + X-Sandbox-Secret), nunca hace commit y lo cierra con
  DELETE /test-control/runs/{run_id}. El run se cierra solo a los 180 s: la biblioteca lleva el reloj y deja
  los casos que no alcanzan como NO CONCLUYENTE.
- Los logins van FUERA del sandbox (dentro del run solo funciona el primero) y el token se reutiliza dentro.
- El Contador se obtiene cambiando el rol de la cuenta del ingeniero (PATCH /usuarios/158, id_rol=5) dentro del run.
- La BD solo se consulta con SELECT por POST /test-control/query. No hay mocks ni fallas inyectadas.
- Lo que no se puede ejecutar queda SKIPPED con una etiqueta: BLOQUEADO / SIN DATOS / NO VERIFICABLE / NO CONCLUYENTE.

Variables de entorno (nunca van en el repositorio):
    TEST_SANDBOX_SECRET            secreto del sandbox (sin él todo queda SKIPPED)
    QA_CONTRASENA_ADMIN            contraseña de admin@pecuaria.co
    QA_CONTRASENA_INGENIERO        contraseña de ingedecampo6@gmail.com (se vuelve Contador dentro del run)
    QA_CONTRASENA_PRODUCTOR        contraseña de daniiella.vargass@gmail.com (solo los grupos de roles)
    QA_CONTRASENA_VETERINARIO      contraseña de mariajosecastillovargas57@gmail.com (solo los grupos de roles)
Opcionales: BASE_URL, QA_CORREO_ADMIN/INGENIERO/PRODUCTOR/VETERINARIO, QA_ID_FINCA (163).
"""
from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any, Optional
from datetime import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "https://api.inmero.co/api-sgpmp-test").rstrip("/")
if BASE_URL.endswith("/sigab"):
    pytest.exit("BASE_URL apunta a MAIN (/sigab): ese ambiente nunca se prueba.", returncode=2)
SECRETO = os.getenv("TEST_SANDBOX_SECRET", "")
TZ = "America/Bogota"
TIMEOUT = 40
LIMITE_RUN_S = 170          # el backend cierra el run a los 180 s
ID_FINCA = int(os.getenv("QA_ID_FINCA", "163"))
TOKEN_INVALIDO = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZXhwIjoxfQ.firma-invalida"

CUENTAS = {
    "admin": (os.getenv("QA_CORREO_ADMIN", "admin@pecuaria.co"), "QA_CONTRASENA_ADMIN", None),
    "productor": (os.getenv("QA_CORREO_PRODUCTOR", "daniiella.vargass@gmail.com"), "QA_CONTRASENA_PRODUCTOR", 68),
    "veterinario": (os.getenv("QA_CORREO_VETERINARIO", "mariajosecastillovargas57@gmail.com"), "QA_CONTRASENA_VETERINARIO", 157),
    "ingeniero": (os.getenv("QA_CORREO_INGENIERO", "ingedecampo6@gmail.com"), "QA_CONTRASENA_INGENIERO", 158),
}
ROL_INGENIERO, ROL_CONTADOR = 4, 5
# Especie de TEST con métrica y ciclo productivo sembrados (Cachama: métrica PESO en kg): el evento productivo de M02 (RF-43) exige una
# fase activa de un ciclo de M09 y no se pueden crear ciclos con la API de QA. Se pueden cambiar con variables de entorno.
ID_ESPECIE_PRODUCTIVA = int(os.getenv("QA_ID_ESPECIE_PRODUCTIVA", "4"))
ID_METRICA_PRODUCTIVA = int(os.getenv("QA_ID_METRICA_PRODUCTIVA", "16"))
ID_CICLO_PRODUCTIVO = int(os.getenv("QA_ID_CICLO_PRODUCTIVO", "4"))

# Cuentas del plan contable de PRUEBA que se cargan por la API de M09 (matriz RF-109) para la especie del run.
CUENTAS_MATRIZ = {
    ("RECONOCIMIENTO_NACIMIENTO", "UNICO"): ("140105", "425010"),
    ("RECONOCIMIENTO_NACIMIENTO", "TRASLADO"): ("140105", "280505"),
    ("RECONOCIMIENTO_DIFERENCIA", "GANANCIA"): ("140105", "425020"),
    ("RECONOCIMIENTO_DIFERENCIA", "PERDIDA"): ("531520", "140105"),
    ("VARIACION_VR_TB", "GANANCIA"): ("140105", "425030"),
    ("VARIACION_VR_TB", "PERDIDA"): ("531530", "140105"),
    ("VARIACION_VR_PM", "GANANCIA"): ("140105", "425040"),
    ("VARIACION_VR_PM", "PERDIDA"): ("531540", "140105"),
    ("PRODUCTO_AGRICOLA", "UNICO"): ("143005", "425050"),
    ("PRODUCTO_AGRICOLA", "TRASLADO"): ("143005", "140105"),
    ("BAJA_ACTIVO", "UNICO"): ("130505", "140105"),
    ("BAJA_ACTIVO", "PERDIDA"): ("531550", "140105"),
}


# --------------------------------------------------------------------------- utilidades
def hoy() -> date:
    # Windows no trae la base de zonas horarias (paquete tzdata): Bogotá no tiene horario de verano, es UTC-5 fijo.
    try:
        zona = ZoneInfo(TZ)
    except ZoneInfoNotFoundError:
        zona = timezone(timedelta(hours=-5))
    return datetime.now(zona).date()


def dec(x: Any) -> Decimal:
    return Decimal(str(x))


def q4(x: Any) -> Decimal:
    return dec(x).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def trunc2(x: Any) -> Decimal:
    """RF-86: los valores de las líneas de asiento se truncan a 2 decimales."""
    return dec(x).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def neto_esperado(bruto: Any, pcts=("0.02", "0.03", "0.01")) -> Decimal:
    """RF-84: valor neto = bruto - (transporte + comisiones + impuestos), cada componente a 4 decimales."""
    b = q4(bruto)
    return q4(b - sum((q4(b * dec(p)) for p in pcts), Decimal(0)))


def dv_nit(numero: str) -> int:
    pesos = [3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]
    s = sum(int(d) * p for d, p in zip(reversed(numero), pesos))
    r = s % 11
    return r if r < 2 else 11 - r


def bloqueado(m: str):
    pytest.skip(f"BLOQUEADO: {m}")


def sin_datos(m: str):
    pytest.skip(f"SIN DATOS: {m}")


def no_verificable(m: str):
    pytest.skip(f"NO VERIFICABLE: {m}")


def no_concluyente(m: str):
    pytest.skip(f"NO CONCLUYENTE: {m}")


def obs(m: str) -> None:
    print(f"[OBSERVACION] {m}")


class R:
    """Respuesta HTTP con su cuerpo JSON y el tiempo de respuesta en milisegundos."""

    def __init__(self, resp: requests.Response, ms: float) -> None:
        self.status, self.text, self.ms = resp.status_code, resp.text, ms
        try:
            self.data = resp.json()
        except Exception:
            self.data = None

    @property
    def err(self) -> Optional[str]:
        return self.data.get("error_code") if isinstance(self.data, dict) else None

    def get(self, clave, defecto=None):
        return self.data.get(clave, defecto) if isinstance(self.data, dict) else defecto

    def __repr__(self) -> str:
        return f"HTTP {self.status} {self.text[:350]}"


def uno(filas: list) -> Any:
    """Primer valor de la primera fila de un resultado de /test-control/query."""
    if not filas:
        return None
    f = filas[0]
    return next(iter(f.values())) if isinstance(f, dict) else f[0]


def _lista(d: Any, *claves: str) -> list:
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        for k in claves + ("items", "eventos", "resultados", "rows", "data"):
            if isinstance(d.get(k), list):
                return d[k]
    return []


lista_de = _lista      # alias público (los scripts importan con *, que no trae nombres con guion bajo)


# --------------------------------------------------------------------------- escenario de datos
@dataclass
class Esc:
    id_especie: int
    id_infra: int
    nombre: str
    categoria: str = "POR_CABEZA"
    precio: Optional[Decimal] = None
    id_precio: Optional[int] = None
    cuentas: dict = field(default_factory=dict)
    asignaciones: dict = field(default_factory=dict)   # (tipo_hecho, sentido) -> id_asignacion_cuenta_contable


def _letras(n: int = 8) -> str:
    """Sufijo aleatorio solo con letras: el backend rechaza nombres con números o símbolos (VAL_ENTRADA)."""
    return "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:n])


class Entorno:
    """Un run del sandbox con los tokens de los roles pedidos y los ayudantes para crear datos."""

    def __init__(self, roles=("admin", "ingeniero")) -> None:
        if not SECRETO:
            bloqueado("falta TEST_SANDBOX_SECRET (secreto del sandbox).")
        self.run_id = "test-pytest-" + uuid.uuid4().hex
        self.inicio: Optional[float] = None
        self.tokens: dict[str, str] = {}
        self.rol_actual: Optional[int] = None
        self._titular = False
        for rol in roles:
            self.tokens[rol] = self._login(rol)

    # ---- sesión y HTTP
    def _login(self, rol: str) -> str:
        correo, var, _ = CUENTAS[rol]
        clave = os.getenv(var, "")
        if not clave:
            bloqueado(f"falta la variable {var} (contraseña del rol {rol}).")
        r = requests.post(f"{BASE_URL}/sesiones/", json={"correo_electronico": correo, "contrasena": clave}, timeout=TIMEOUT)
        if r.status_code != 200:
            bloqueado(f"login de {rol} ({correo}) respondió {r.status_code}: {r.text[:160]}")
        return r.json()["token"]

    def restante(self) -> float:
        return LIMITE_RUN_S - (time.time() - self.inicio) if self.inicio else LIMITE_RUN_S

    def presupuesto(self, segundos: float = 25) -> None:
        if self.restante() < segundos:
            no_concluyente(f"se agotó el presupuesto de {LIMITE_RUN_S} s del sandbox (quedan {self.restante():.0f} s).")

    def call(self, metodo: str, ruta: str, rol: Optional[str] = None, json: Any = None, params: Any = None,
             token: Optional[str] = None, sandbox: bool = True) -> R:
        h = {"X-Zona-Horaria": TZ}
        tok = token or (self.tokens.get(rol) if rol else None)
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        if sandbox:
            h["X-Test-Run-Id"], h["X-Sandbox-Secret"] = self.run_id, SECRETO
            if self.inicio is None:
                self.inicio = time.time()
        t0 = time.time()
        resp = requests.request(metodo, f"{BASE_URL}{ruta}", headers=h, json=json, params=params, timeout=TIMEOUT)
        return R(resp, (time.time() - t0) * 1000)

    def prep(self, r: R, codigos, que: str) -> R:
        """Precondición: si falla, el caso queda BLOQUEADO (no es un defecto del caso)."""
        if r.status not in codigos:
            bloqueado(f"precondición «{que}» respondió {r}")
        return r

    def cerrar(self) -> None:
        if self.inicio is not None:
            try:
                self.call("DELETE", f"/test-control/runs/{self.run_id}")
            except Exception:
                pass

    def nuevo_run(self) -> None:
        """Cierra el run actual (rollback) y abre uno nuevo con el reloj en cero. Los tokens se conservan: los logins
        van fuera del sandbox y el rol de la cuenta del ingeniero vuelve a su valor original con el rollback."""
        self.cerrar()
        self.run_id = "test-pytest-" + uuid.uuid4().hex
        self.inicio = None
        self.rol_actual = None
        self._titular = False

    def asignar_fase(self, id_activo: int) -> R:
        """Asigna la fase activa del ciclo productivo (RF-37) al activo y devuelve la respuesta (sin exigir éxito)."""
        return self.call("POST", f"/activos-biologicos/{id_activo}/fases", "admin",
                         json={"id_ciclo_productiva": ID_CICLO_PRODUCTIVO})

    def sql(self, consulta: str) -> list[dict]:
        r = self.call("POST", "/test-control/query", json={"query": consulta})
        assert r.status == 200, f"/test-control/query respondió {r}"
        filas = _lista(r.data, "filas")
        return [f if isinstance(f, dict) else {"c%d" % i: v for i, v in enumerate(f)} for f in filas]

    # ---- roles
    def set_rol(self, id_rol: int) -> None:
        """Cambia el rol de la cuenta del ingeniero (id 158) dentro del run; el rollback lo restaura."""
        if self.rol_actual == id_rol:
            return
        uid = CUENTAS["ingeniero"][2]
        d = self.prep(self.call("GET", f"/usuarios/{uid}/detalle", "admin"), (200,), "detalle del usuario 158")
        cuerpo = {"nombre": d.get("nombre"), "apellidos": d.get("apellidos"), "version": d.get("version"), "id_rol": id_rol}
        self.prep(self.call("PATCH", f"/usuarios/{uid}", "admin", json=cuerpo), (200,), f"PATCH rol {id_rol} del usuario 158")
        self.rol_actual = id_rol

    def contador(self) -> None:
        self.set_rol(ROL_CONTADOR)
        self.tokens["contador"] = self.tokens["ingeniero"]

    def titular(self) -> None:
        if self._titular:
            return
        r = self.call("GET", f"/configuracion/fincas/{ID_FINCA}/titular", "admin")
        if r.status == 200 and (r.get("numero_id_tributaria") or (r.data or {}).get("titular")):
            self._titular = True
            return
        nit = "900123456"
        self.prep(self.call("PUT", f"/configuracion/fincas/{ID_FINCA}/titular", "admin", json={
            "tipo_id_tributaria": "NIT", "numero_id_tributaria": nit, "dv": str(dv_nit(nit)),
            "razon_social": "QA Titular M06"}), (200, 201), "titular tributario de la finca")
        self._titular = True

    # ---- datos del run
    def escenario(self, categoria: str = "POR_CABEZA", clasificacion: Optional[str] = "PRODUCCION",
                  costos=("0.02", "0.03", "0.01"), precio: Optional[str] = "8000000.00", fuente: str = "MERCADO_ACTIVO",
                  vida_util: Optional[int] = 60, matriz: bool = True, especie_existente: Optional[int] = None) -> Esc:
        """Especie + infraestructura nuevas en la finca de pruebas, con (o sin) clasificación, costos de venta,
        precio RF-89 y matriz contable. Cada escenario es independiente de los demás."""
        self.titular()
        self.contador()
        suf = _letras(8)
        if especie_existente:
            id_esp = especie_existente
        else:
            a = self.prep(self.call("POST", "/configuracion/especies", "admin", json={
                "nombre": f"Especie QA {suf}", "descripcion": "Especie de prueba TC-M06",
                "densidad_maxima_por_especie": "50.00", "grupo_manejo": "PORCINOS"}), (200, 201), "crear especie")
            id_esp = a.get("id_especie")
        i = self.prep(self.call("POST", "/configuracion/infraestructuras", "admin", json={
            "nombre_infraestructura": f"Galpon QA {suf}", "tipo_area": "Galpón", "superficie": "500.00",
            "finca_id": ID_FINCA, "especie_id": id_esp}), (200, 201), "crear infraestructura")
        esc = Esc(id_esp, i.get("id_infraestructura"), f"Especie QA {suf}", categoria)
        if clasificacion:
            cuerpo = {"clasificacion": clasificacion, "categoria_precio": categoria}
            if vida_util:
                cuerpo["vida_util_meses"] = vida_util
            self.prep(self.call("PUT", f"/finanzas/configuracion/especies/{id_esp}", "contador", json=cuerpo), (200, 201), "parámetros de la especie (M09)")
        if costos:
            self.prep(self.call("PUT", f"/finanzas/configuracion/costos-venta/{id_esp}", "contador", json={
                "pct_transporte": costos[0], "pct_comisiones": costos[1], "pct_impuestos": costos[2]}), (200, 201), "costos de venta (M09)")
        if matriz:
            for (tipo, sentido), (deb, cre) in CUENTAS_MATRIZ.items():
                r = self.call("POST", "/finanzas/configuracion/matriz", "contador", json={
                    "tipo_hecho": tipo, "sentido": sentido, "id_especie": id_esp, "cuenta_debito": deb, "cuenta_credito": cre})
                if r.status in (200, 201):
                    esc.cuentas[(tipo, sentido)] = (deb, cre)
                    esc.asignaciones[(tipo, sentido)] = r.get("id_asignacion_cuenta_contable")
        if precio:
            self.precio(esc, precio, fuente)
        return esc

    def precio(self, esc: Esc, valor: str, fuente: str = "MERCADO_ACTIVO", desde: Optional[date] = None,
               categoria: Optional[str] = None, id_corregido: Optional[int] = None, hasta: Optional[date] = None) -> R:
        cuerpo = {"id_especie": esc.id_especie, "categoria": categoria or esc.categoria, "precio_unitario": valor,
                  "fecha_vigencia": str(desde or (hoy() - timedelta(days=1))), "fuente": fuente,
                  "evidencia_documental": "Boletín de precios QA TC-M06", "confirmar_desviacion": True}
        if fuente == "ESTIMADA":
            cuerpo["justificacion_estimacion"] = "Sin precio de mercado activo ni UPRA; comparables de la región usados en la estimación QA."
        if id_corregido:
            cuerpo["id_precio_corregido"] = id_corregido
        if hasta:
            cuerpo["fecha_vencimiento"] = str(hasta)
        r = self.prep(self.call("POST", "/finanzas/precios", "contador", json=cuerpo), (200, 201), "registrar precio RF-89")
        if (categoria or esc.categoria) == esc.categoria:
            esc.precio, esc.id_precio = dec(valor), r.get("id_precio_mercado")
        return r

    def activo_r(self, esc: Esc, origen: str = "compra", costo: Optional[str] = "2500000.0000",
                 soporte: Optional[str] = "Factura QA-M06", tipo: str = "INDIVIDUAL", cantidad: int = 10,
                 peso_promedio: str = "50", quitar: tuple = (), **extra) -> R:
        cuerpo: dict = {"tipo_activo": tipo, "id_especie": esc.id_especie, "id_infraestructura": esc.id_infra,
                        "fecha_inicio_ciclo": str(hoy()), "origen_financiero": origen}
        if costo is not None:
            cuerpo["costo_adquisicion"] = costo
        if soporte is not None:
            cuerpo["soporte_documental"] = soporte
        if tipo == "INDIVIDUAL":
            cuerpo.update({"identificador": f"QA-M06-{uuid.uuid4().hex[:10]}", "raza": "QA", "sexo": "Macho"})
        else:
            cuerpo.update({"cantidad_inicial": cantidad, "peso_promedio_inicial": peso_promedio})
        cuerpo.update(extra)
        for k in quitar:
            cuerpo.pop(k, None)
        return self.call("POST", "/activos-biologicos", "admin", json=cuerpo)

    def activo(self, esc: Esc, peso_kg: Optional[str] = None, **kw) -> int:
        """Registra el activo por RF-33 (como Administrador). Con categoría PESO_KG registra también el pesaje."""
        r = self.prep(self.activo_r(esc, **kw), (200, 201), f"registrar activo RF-33 ({kw})")
        ida = r.get("id_activo_biologico")
        if esc.categoria == "PESO_KG" and kw.get("tipo", "INDIVIDUAL") == "INDIVIDUAL":
            self.pesaje(ida, peso_kg or "400")
        return ida

    def pesaje(self, id_activo: int, kg: str) -> R:
        return self.prep(self.call("POST", f"/activos-biologicos/{id_activo}/eventos/crecimiento", "admin", json={
            "tipo_medicion": "PESO", "valor_medicion": kg, "unidad_medida": "kg"}), (200, 201), "evento de crecimiento (pesaje)")

    def baja(self, id_activo: int, tipo: str = "perdida", cantidad: Optional[int] = None) -> R:
        cuerpo = {"tipo_baja": tipo, "fecha_baja": str(hoy()), "motivo_baja": "Baja por prueba QA TC-M06"}
        if cantidad:
            cuerpo["cantidad_afectada"] = cantidad
        return self.call("POST", f"/activos-biologicos/{id_activo}/eventos/baja", "admin", json=cuerpo)

    def estado_activo(self, id_activo: int, estado: str) -> R:
        return self.call("PATCH", f"/activos-biologicos/{id_activo}/estado", "admin", json={
            "estado_nuevo": estado, "fecha_cambio_estado": str(hoy()), "motivo_cambio": "Cambio de estado por prueba QA TC-M06"})

    # ---- M06
    def propuesta(self, id_activo: int, rol: str = "contador", **params) -> R:
        return self.call("GET", f"/finanzas/reconocimientos/propuestas/{id_activo}", rol, params=params or None)

    def confirmar(self, id_activo: int, rol: str = "contador", cuerpo: Optional[dict] = None) -> R:
        return self.call("POST", f"/finanzas/reconocimientos/{id_activo}", rol, json=cuerpo if cuerpo is not None else {})

    def revertir(self, id_activo: int, motivo: str, rol: str = "contador") -> R:
        return self.call("POST", f"/finanzas/reconocimientos/{id_activo}/reversion", rol, json={"motivo_reversion": motivo})

    def reconocer(self, esc: Esc, **kw) -> tuple[int, R]:
        """Activo nuevo + confirmación del reconocimiento por el Contador. Devuelve (id_activo, respuesta)."""
        ida = self.activo(esc, **kw)
        r = self.prep(self.confirmar(ida), (200, 201), "confirmar el reconocimiento inicial")
        return ida, r

    def historial(self, id_activo: int) -> dict:
        r = self.call("GET", f"/finanzas/activos/{id_activo}", "contador")
        assert r.status == 200, f"GET /finanzas/activos/{id_activo} respondió {r}"
        return r.data

    def auditoria(self, id_activo: int, tipo: Optional[str] = None) -> list[dict]:
        params: dict = {"id_activo_biologico": id_activo, "tamano": 500}
        if tipo:
            params["tipo_evento"] = tipo
        r = self.call("GET", "/finanzas/auditoria", "contador", params=params)
        assert r.status == 200, f"GET /finanzas/auditoria respondió {r}"
        return _lista(r.data, "eventos")

    def tipos_auditoria(self, id_activo: int) -> list[str]:
        return [e.get("tipo_evento") for e in self.auditoria(id_activo)]

    def procesar_eventos(self) -> R:
        return self.call("POST", "/finanzas/eventos/procesar", "contador")

    def simulacion(self, id_activo: int) -> R:
        return self.call("GET", f"/finanzas/activos/{id_activo}/simulacion", "contador")

    def medir(self, esc: Esc, id_activo: int, nuevo_precio: Optional[str] = None, kg: str = "450") -> R:
        """Dispara una medición posterior por evento: (opcional) precio nuevo vigente desde hoy + evento de crecimiento de M02
        + procesamiento de la cola de eventos. Antes vacía la cola (los eventos previos al cambio ya no miden nada).
        Devuelve la respuesta de POST /finanzas/eventos/procesar del evento nuevo."""
        self.procesar_eventos()
        if nuevo_precio:
            self.precio(esc, nuevo_precio, desde=hoy())
        self.pesaje(id_activo, kg)
        return self.procesar_eventos()

    def mediciones(self, id_activo: int) -> list[dict]:
        """Mediciones posteriores del activo en orden de creación (la fecha es igual dentro de una transacción)."""
        return sorted(self.historial(id_activo).get("mediciones") or [], key=lambda m: m["id_medicion_posterior"])

    def base_medible(self, esc: Esc, kg: str = "400", **kw) -> int:
        """Activo reconocido (por nacimiento) con su cola de eventos vacía: listo para medir."""
        ida, _ = self.reconocer(esc, origen="nacimiento", costo=None, soporte=None, peso_kg=kg, **kw)
        self.procesar_eventos()
        return ida

    def ultimo_evento(self, id_activo: int) -> Optional[int]:
        v = uno(self.sql(f"SELECT max(id_eventos) FROM modulo2.eventos_activos WHERE id_activo_biologico = {int(id_activo)}"))
        return int(v) if v is not None else None

    def metrica(self, esc: Esc, nombre: str = "Leche QA", unidad: str = "kg", tipo: str = "PESO") -> int:
        r = self.prep(self.call("POST", "/configuracion/metricas", "admin", json={
            "id_especie": esc.id_especie, "nombre": f"{re.sub(r'[^A-Za-zÁÉÍÓÚáéíóúÑñ ]', '', nombre).strip()} {_letras(4)}", "unidad_medida": unidad, "tipo_medicion": tipo,
            "aplica_a_tipo_activo": "AMBOS", "tipo_dato": "NUMERICO", "es_obligatorio": False}), (200, 201), "crear métrica de producción (M09)")
        return r.get("id_metrica_produccion")

    def evento_productivo(self, id_activo: int, id_metrica: int, cantidad: str, unidad: str) -> R:
        return self.prep(self.call("POST", f"/activos-biologicos/{id_activo}/eventos/productivo", "admin", json={
            "id_metrica_produccion": id_metrica, "cantidad_producida": cantidad, "unidad_medida": unidad,
            "fecha_evento": str(hoy())}), (200, 201), "evento productivo RF-43")

    def precio_producto(self, esc: Esc, id_metrica: int, valor: str, desde: Optional[date] = None) -> R:
        return self.prep(self.call("POST", "/finanzas/precios", "contador", json={
            "id_especie": esc.id_especie, "categoria": "PRODUCTO", "id_metrica_produccion": id_metrica, "precio_unitario": valor,
            "fecha_vigencia": str(desde or (hoy() - timedelta(days=1))), "fuente": "MERCADO_ACTIVO",
            "evidencia_documental": "Boletín producto QA TC-M06", "confirmar_desviacion": True}), (200, 201), "precio del producto RF-89")

    def cierre(self, id_periodo: int) -> R:
        """RF-87: cierra el período dentro del run. Si no responde a tiempo, el caso queda NO CONCLUYENTE."""
        try:
            return self.call("POST", f"/finanzas/periodos/{id_periodo}/cierre", "contador",
                             json={"autorizar_exclusiones": True, "incluir_activos_sin_precio": True})
        except requests.exceptions.RequestException as exc:
            no_concluyente(f"el cierre del período no respondió a tiempo dentro del sandbox: {exc}")

    # ---- RF-85 (producto agrícola)
    def escenario_producto(self, clasificacion: str = "PRODUCCION", precio_activo: str = "20000.00",
                           precio_producto: Optional[str] = None, costos=("0.02", "0.03", "0.01")) -> Esc:
        """Escenario sobre la especie productiva sembrada de TEST (precios vigentes desde hace 10 días)."""
        esc = self.escenario(categoria="PESO_KG", clasificacion=clasificacion, costos=costos, precio=None,
                             especie_existente=ID_ESPECIE_PRODUCTIVA)
        if precio_activo:
            self.precio(esc, precio_activo, desde=hoy() - timedelta(days=10))
        if precio_producto:
            self.precio_producto(esc, ID_METRICA_PRODUCTIVA, precio_producto, desde=hoy() - timedelta(days=10))
        return esc

    def activo_productivo(self, esc: Esc, kg: str = "1000") -> int:
        """Activo reconocido, con la cola vacía y con una fase activa (RF-37) que habilita el evento productivo (RF-43)."""
        ida, _ = self.reconocer(esc, origen="nacimiento", costo=None, soporte=None, peso_kg=kg)
        self.procesar_eventos()
        r = self.call("POST", f"/activos-biologicos/{ida}/fases", "admin", json={"id_ciclo_productiva": ID_CICLO_PRODUCTIVO})
        if r.status >= 500:
            bloqueado(f"RF-37 (asignar fase al activo) responde {r.status}: sin fase activa M02 no acepta eventos productivos (defecto previo de M02).")
        if r.status not in (200, 201):
            bloqueado(f"no se pudo asignar la fase del ciclo {ID_CICLO_PRODUCTIVO} al activo: {r}")
        return ida

    def cosecha(self, id_activo: int, cantidad: str, unidad: str = "kg", fecha: Optional[date] = None) -> R:
        """Evento productivo (RF-43) sin exigir éxito: devuelve la respuesta."""
        return self.call("POST", f"/activos-biologicos/{id_activo}/eventos/productivo", "admin", json={
            "id_metrica_produccion": ID_METRICA_PRODUCTIVA, "cantidad_producida": cantidad, "unidad_medida": unidad,
            "fecha_evento": str(fecha or hoy())})

    def cosechar(self, id_activo: int, cantidad: str, unidad: str = "kg") -> R:
        """Evento productivo exitoso + procesamiento de la cola. Si M02 rechaza el evento, la precondición queda BLOQUEADA."""
        self.prep(self.cosecha(id_activo, cantidad, unidad), (200, 201), "evento productivo RF-43")
        return self.procesar_eventos()

    def productos(self, id_activo: int) -> list[dict]:
        return sorted(self.historial(id_activo).get("productos") or [], key=lambda p: p["id_reconocimiento_producto_agricola"])

    def producto_sql(self, id_activo: int) -> list[dict]:
        return self.sql("SELECT id_reconocimiento_producto_agricola AS id, id_evento_productivo, cantidad_cosechada, unidad_medida, "
                        "precio_mercado_producto, costo_venta_producto, valor_producto, proporcion_cosechada, valor_reduccion_activo, "
                        "tipo::text AS tipo, id_periodo_contable FROM modulo6.reconocimientos_productos_agricolas "
                        f"WHERE id_activo_biologico = {int(id_activo)} ORDER BY 1")

    def lineas_producto(self, id_activo: int) -> list[dict]:
        return self.sql("SELECT tipo_hecho::text AS tipo_hecho, sentido::text AS sentido, valor, cuenta_debito, cuenta_credito, id_origen, estado::text AS estado "
                        f"FROM modulo6.lineas_asiento_nic41 WHERE id_activo_biologico = {int(id_activo)} AND NOT es_reverso "
                        "AND tipo_hecho::text = 'PRODUCTO_AGRICOLA' ORDER BY 1")

    def calculo(self, id_activo: int) -> Optional[dict]:
        """Último cálculo RF-84 persistido del activo (componentes, método, neto, estado)."""
        cs = self.historial(id_activo).get("calculos") or []
        return max(cs, key=lambda c: c["id_calculo_valor_razonable"]) if cs else None

    def confirmar_manual(self, esc: Esc, manuales: Optional[dict] = None, justificacion: Optional[str] = None,
                         clasificacion: Optional[str] = None, **kw) -> tuple[int, R]:
        """Activo de nacimiento nuevo + confirmación con costos manuales opcionales. No exige éxito: devuelve (id, respuesta)."""
        ida = self.activo(esc, origen="nacimiento", costo=None, soporte=None, **kw)
        cuerpo: dict = {}
        if manuales is not None:
            cuerpo["costos_manuales"] = manuales
        if justificacion is not None:
            cuerpo["justificacion"] = justificacion
        if clasificacion:
            cuerpo["clasificacion"] = clasificacion
        return ida, self.confirmar(ida, cuerpo=cuerpo)

    def periodo(self, id_activo: int) -> Optional[int]:
        """Período contable del último cálculo del activo (SELECT de solo lectura)."""
        v = uno(self.sql("SELECT id_periodo_contable FROM modulo6.calculos_valor_razonable "
                         f"WHERE id_activo_biologico = {int(id_activo)} ORDER BY id_calculo_valor_razonable DESC LIMIT 1"))
        return int(v) if v is not None else None

    def contar(self, tabla: str, id_activo: int, extra: str = "") -> int:
        """SELECT count(*) sobre una tabla de modulo6 filtrada por activo (solo lectura, vía /test-control/query)."""
        filas = self.sql(f"SELECT count(*) AS n FROM modulo6.{tabla} WHERE id_activo_biologico = {int(id_activo)} {extra}")
        return int(uno(filas) or 0)


# --------------------------------------------------------------------------- comprobaciones frecuentes
def codigos(prop: R) -> list[str]:
    return [b.get("codigo") for b in (prop.get("bloqueos") or [])]


def lineas_de(hist: dict) -> list[dict]:
    return hist.get("lineas") or []


def hechos(prop: R) -> list[tuple]:
    return [(h.get("tipo_hecho"), h.get("sentido"), dec(h.get("valor"))) for h in (prop.get("hechos") or [])]


def verificar_asiento(lineas: list[dict]) -> None:
    """RF-86: cada línea lleva un par débito/crédito distinto y un valor positivo."""
    for ln in lineas:
        assert dec(ln.get("valor")) > 0, f"línea con valor no positivo: {ln}"
        if ln.get("estado") == "REGISTRADA":
            assert ln.get("cuenta_debito") and ln.get("cuenta_credito"), f"línea REGISTRADA sin par de cuentas: {ln}"
            assert ln["cuenta_debito"] != ln["cuenta_credito"], f"cuentas iguales en la línea: {ln}"


def vn(magnitud: Any, precio: Any, pcts=("0.02", "0.03", "0.01")) -> Decimal:
    """Valor neto RF-84 de una magnitud a un precio (fórmula del RF)."""
    return neto_esperado(dec(magnitud) * dec(precio), pcts)


def efectos(vn_ant: Decimal, vn_act: Decimal, mag_ant: Any, precio_nuevo: Any, pcts=("0.02", "0.03", "0.01")) -> tuple[Decimal, Decimal]:
    """RF-83 pasos 4-6: (efecto precio, efecto transformación). pre_evento_ajustado = valor con la magnitud ANTERIOR y el precio NUEVO."""
    pre = vn(mag_ant, precio_nuevo, pcts)
    precio = q4(pre - vn_ant)
    return precio, q4(vn_act - vn_ant) - precio


def cerca(a: Any, b: Any, tol: str = "0.0002") -> bool:
    return abs(dec(a) - dec(b)) <= dec(tol)
