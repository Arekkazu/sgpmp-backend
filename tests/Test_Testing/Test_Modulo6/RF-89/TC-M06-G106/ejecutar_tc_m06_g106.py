# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-11 | —      | Preparación previa a RF-89 v1.2 (desviación vs vigente). |
# | 2026-11-12 | —      | Ajuste a RF-89 v1.2 / PR #1074: herencia de vigencia y estados. |
"""TC-M06-G106, subcaso TC-M06-30 y negativos de corrección (RF-89 FA-6).

Reglas confirmadas (Alex / PR #1074 / RF-89 v1.2):
- La corrección hereda la fecha de vigencia del original; no se envía otra.
- La desviación se mide contra el precio corregido (436 = 4.000.000).
- El original queda CORREGIDO; la corrección histórica queda SUPERADO;
  el 645 permanece ACTIVO y aplicado.
- Sin fecha de vencimiento en el escenario positivo.

Orden de ejecución (sin duplicar el POST positivo):
1. Negativo fuente distinta → 400 CORRECCION_NO_COINCIDE
2. Negativo fecha distinta → 400 FECHA_VIGENCIA_CORRECCION
3. Positivo importe 4.200.000 sin fecha_vigencia → 201
4. Negativo segunda corrección de 436 → 409 PRECIO_YA_CORREGIDO

La primera evaluación del 8-nov queda en resultados/primera_evaluacion/.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

CARPETA = Path(__file__).resolve().parent
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ESPECIE = 424
CATEGORIA = "POR_CABEZA"
FUENTE = "MERCADO_ACTIVO"
CORREGIDO = 436
APLICADO = 645
UMBRAL_ESPERADO = Decimal("50.00")
IMPORTE_CORRECCION = Decimal("4200000.00")
IMPORTE_ORIGINAL = Decimal("4000000.00")
DESVIACION_ESPERADA = Decimal("5")
VIGENCIA_ORIGINAL = "2026-11-01"
VIGENCIA_APLICADO = "2026-11-11"
CENT = Decimal("0.01")
EVIDENCIA = (
    "TC-M06-30 correccion historica del precio 436 a 4200000.00 sin fecha_vigencia "
    "ni vencimiento, conforme RF-89 v1.2 / PR 1074."
)
CAMPOS_ALMACENADOS = (
    "id_especie", "categoria", "fuente", "precio_unitario", "fecha_vigencia",
    "fecha_vencimiento", "id_metrica_produccion", "id_precio_corregido",
)
PROTEGIDOS = {
    "evidencia_peticiones_TC-M06-G106.json",
    "resultado_ejecucion_TC-M06-G106.html",
    "resumen_ejecucion_TC-M06-G106.json",
}
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria"}


class ResultadoIncierto(Exception):
    """La petición no tuvo una respuesta HTTP definitiva. No se reintenta un POST."""


def hoy_bogota() -> date:
    return datetime.now(ZoneInfo(ZONA)).date()


def decimal(valor) -> Decimal:
    return Decimal(str(valor))


def desviacion(nuevo: Decimal, referencia: Decimal) -> Decimal:
    return abs(nuevo - referencia) / referencia * Decimal("100")


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, indent=2, default=str)


def limpiar(valor, profundidad: int = 0):
    if profundidad > 6:
        return "..."
    if isinstance(valor, dict):
        return {
            clave: ({"omitido": True} if clave in SECRETOS else limpiar(contenido, profundidad + 1))
            for clave, contenido in valor.items()
        }
    if isinstance(valor, list):
        return [limpiar(item, profundidad + 1) for item in valor[:80]]
    if isinstance(valor, str) and len(valor) > 400:
        return valor[:400]
    return valor


def ruta_salida(carpeta: Path, fase: str, nombre: str) -> Path:
    if nombre in PROTEGIDOS:
        raise RuntimeError(f"Nombre reservado de la evaluación histórica: {nombre}")
    if fase not in {"preparacion", "ultima"}:
        raise RuntimeError("Fase de evidencia desconocida.")
    subcarpeta = "soporte_preparacion" if fase == "preparacion" else "ultima_evaluacion"
    destino = carpeta / "resultados" / subcarpeta / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    return destino


def guardar(carpeta: Path, fase: str, resumen: dict, peticiones: list) -> None:
    prefijo = "preparacion" if fase == "preparacion" else "ejecucion_vigente"
    (ruta_salida(carpeta, fase, f"resumen_{prefijo}_TC-M06-G106.json")).write_text(_json(resumen), encoding="utf-8")
    (ruta_salida(carpeta, fase, f"evidencias_{prefijo}_TC-M06-G106.json")).write_text(
        _json({"caso": "TC-M06-G106", "fase": fase, "peticiones": limpiar(peticiones)}), encoding="utf-8")
    (ruta_salida(carpeta, fase, f"resultado_{prefijo}_TC-M06-G106.html")).write_text(
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>TC-M06-G106</title></head><body>"
        f"<h1>TC-M06-G106 — {resumen.get('fase')}</h1>"
        f"<p>Dictamen: {resumen.get('dictamen_general')}. "
        f"Caso completo aprobado: {resumen.get('caso_completo_aprobado')}.</p>"
        f"<pre>{_json(resumen)}</pre></body></html>",
        encoding="utf-8",
    )


def _igual_decimal(origen, destino) -> bool:
    if origen is None or destino is None:
        return origen is None and destino is None
    return decimal(origen) == decimal(destino)


def almacenado_igual(fila: dict, otra: dict) -> bool:
    for campo in CAMPOS_ALMACENADOS:
        if campo == "precio_unitario":
            if not _igual_decimal(fila.get(campo), otra.get(campo)):
                return False
        elif fila.get(campo) != otra.get(campo):
            return False
    return True


def _fila(precios: list, identificador: int) -> dict | None:
    return next((precio for precio in precios if precio.get("id_precio_mercado") == identificador), None)


def _resumen_precio(precio: dict | None) -> dict | None:
    if not isinstance(precio, dict):
        return None
    return {
        clave: precio.get(clave)
        for clave in (
            "id_precio_mercado", "precio_unitario", "fecha_vigencia", "fecha_vencimiento",
            "estado", "es_aplicado", "id_precio_corregido", "fuente", "categoria", "id_especie",
        )
    }


class ClienteUrllib:
    def pedir(self, metodo: str, ruta: str, cuerpo: dict | None = None, token: str | None = None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode()
        headers = {"Accept": "application/json", "X-Zona-Horaria": ZONA}
        if cuerpo is not None:
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(BASE_API + ruta, data=datos, headers=headers, method=metodo)
        inicio = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode()
                payload = json.loads(raw) if raw else None
                codigo = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw[:200]}
            codigo = exc.code
        except (TimeoutError, urllib.error.URLError) as exc:
            raise ResultadoIncierto(f"{metodo} {ruta}") from exc
        return codigo, payload, round((time.perf_counter() - inicio) * 1000)


def _registrar(peticiones: list, metodo: str, ruta: str, codigo, payload, escenario: str | None = None) -> None:
    entrada = {"metodo": metodo, "consulta": ruta, "codigo": codigo, "respuesta": limpiar(payload)}
    if escenario:
        entrada["escenario"] = escenario
    peticiones.append(entrada)


def _get(cliente, ruta: str, token: str, peticiones: list, escenario: str | None = None):
    try:
        codigo, payload, _ = cliente.pedir("GET", ruta, token=token)
    except ResultadoIncierto:
        _registrar(peticiones, "GET", ruta, None, {"incierto": True}, escenario)
        return None, None
    _registrar(peticiones, "GET", ruta, codigo, payload, escenario)
    return codigo, payload


def _post(cliente, cuerpo: dict, token: str, peticiones: list, escenario: str,
          registro: list | None = None, permitir_confirmacion: bool = False) -> dict:
    if registro is not None:
        intentos_previos = len(registro)
        if intentos_previos >= 1 and not (permitir_confirmacion and intentos_previos == 1):
            raise RuntimeError("Reenvío del POST positivo prohibido.")
        if intentos_previos >= 2:
            raise RuntimeError("Solo se admite un reintento con confirmar_desviacion.")
        registro.append(cuerpo.get("precio_unitario"))
    try:
        codigo, payload, _ = cliente.pedir("POST", "/finanzas/precios", cuerpo, token)
    except ResultadoIncierto as exc:
        _registrar(peticiones, "POST", "/finanzas/precios", None, {"incierto": True, "cuerpo": limpiar(cuerpo)}, escenario)
        return {"incierto": True, "codigo": None, "payload": None, "detalle": str(exc)}
    _registrar(
        peticiones, "POST", "/finanzas/precios", codigo,
        {"cuerpo": limpiar(cuerpo), "respuesta": limpiar(payload)}, escenario,
    )
    return {"incierto": codigo is None or codigo >= 500, "codigo": codigo, "payload": payload, "detalle": None}


def _codigo_error(payload) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("error_code") or payload.get("code")


def umbral_de(configuracion: dict) -> Decimal | None:
    general = configuracion.get("general") if isinstance(configuracion, dict) else None
    if not isinstance(general, dict) or general.get("pct_umbral_desviacion_precio") is None:
        return None
    return decimal(general["pct_umbral_desviacion_precio"])


def especie_valida(catalogo: dict, configuracion: dict) -> bool:
    items = catalogo.get("items") if isinstance(catalogo, dict) else None
    especie = next((item for item in items or [] if item.get("id_especie") == ESPECIE), None)
    if not isinstance(especie, dict) or not especie.get("es_activo"):
        return False
    parametros = configuracion.get("especies") if isinstance(configuracion, dict) else None
    parametro = next((item for item in parametros or [] if item.get("id_especie") == ESPECIE), None)
    return isinstance(parametro, dict) and parametro.get("categoria_precio") == CATEGORIA


def _precondiciones(precios: list, configuracion: dict) -> tuple[dict | None, str]:
    umbral = umbral_de(configuracion)
    if umbral != UMBRAL_ESPERADO:
        return None, f"El umbral vigente no es 50.00 (leído: {umbral})."
    original = _fila(precios, CORREGIDO)
    aplicado = _fila(precios, APLICADO)
    if original is None:
        return None, "No aparece el precio 436."
    if aplicado is None:
        return None, "No aparece el precio 645."
    if any(p.get("id_precio_corregido") == CORREGIDO for p in precios):
        return None, "El precio 436 ya tiene una corrección; el escenario positivo no puede ejecutarse sin duplicar."
    if not _igual_decimal(original.get("precio_unitario"), IMPORTE_ORIGINAL):
        return None, "El importe almacenado del 436 no es 4000000.00."
    if original.get("fecha_vigencia") != VIGENCIA_ORIGINAL or original.get("fecha_vencimiento") is not None:
        return None, "La vigencia/vencimiento del 436 no coinciden con la evidencia de G108."
    if original.get("estado") != "SUPERADO" or bool(original.get("es_aplicado")):
        return None, "El precio 436 no está SUPERADO / no aplicado antes de la corrección."
    if original.get("id_especie") != ESPECIE or original.get("categoria") != CATEGORIA or original.get("fuente") != FUENTE:
        return None, "El precio 436 no es especie 424 / POR_CABEZA / MERCADO_ACTIVO."
    if not _igual_decimal(aplicado.get("precio_unitario"), Decimal("7650000.00")):
        return None, "El importe del 645 no es 7650000.00."
    if aplicado.get("fecha_vigencia") != VIGENCIA_APLICADO or aplicado.get("fecha_vencimiento") is not None:
        return None, "La vigencia/vencimiento del 645 no coinciden con G108."
    if aplicado.get("estado") != "ACTIVO" or not bool(aplicado.get("es_aplicado")):
        return None, "El precio 645 no es ACTIVO y aplicado."
    if desviacion(IMPORTE_CORRECCION, IMPORTE_ORIGINAL) != DESVIACION_ESPERADA:
        return None, "La desviación calculada contra 436 no es 5%."
    return {
        "umbral": umbral,
        "original": original,
        "aplicado": aplicado,
        "precios": precios,
        "desviacion": DESVIACION_ESPERADA,
    }, "listo"


def _leer_base(cliente, token: str, peticiones: list) -> tuple[dict | None, str]:
    codigo_especies, especies = _get(cliente, "/configuracion/especies", token, peticiones, "precondicion")
    codigo_config, configuracion = _get(cliente, "/finanzas/configuracion", token, peticiones, "precondicion")
    codigo_precios, precios = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones, "precondicion")
    if not all(codigo == 200 for codigo in (codigo_especies, codigo_config, codigo_precios)):
        return None, "Alguna lectura previa no respondió HTTP 200."
    if not especie_valida(especies, configuracion):
        return None, "La especie 424 no está activa o no tiene categoría POR_CABEZA."
    if not isinstance(precios, list):
        return None, "El catálogo de la especie 424 no es una lista."
    return _precondiciones(precios, configuracion)


def _cuerpo_positivo(confirmar: bool) -> dict:
    return {
        "id_especie": ESPECIE,
        "categoria": CATEGORIA,
        "fuente": FUENTE,
        "precio_unitario": f"{IMPORTE_CORRECCION:.2f}",
        "evidencia_documental": EVIDENCIA,
        "id_precio_corregido": CORREGIDO,
        "confirmar_desviacion": confirmar,
    }


def _escenario(nombre: str, estado: str, esperado: dict, obtenido: dict, detalle: str | None = None) -> dict:
    return {
        "escenario": nombre,
        "estado": estado,
        "esperado": esperado,
        "obtenido": obtenido,
        "detalle": detalle,
    }


def _verificar_positivo(respuesta: dict, antes: list, despues: list) -> tuple[str | None, dict]:
    if not isinstance(respuesta, dict) or not isinstance(respuesta.get("id_precio_mercado"), int):
        return "La respuesta 201 no trajo un id entero.", {}
    nuevo_id = respuesta["id_precio_mercado"]
    if _fila(antes, nuevo_id) is not None:
        return "El id devuelto ya existía antes del POST.", {}
    nuevo = _fila(despues, nuevo_id)
    original = _fila(despues, CORREGIDO)
    aplicado = _fila(despues, APLICADO)
    if nuevo is None:
        return "El GET posterior no muestra el precio nuevo.", {}
    if int(nuevo.get("id_precio_corregido") or 0) != CORREGIDO:
        return "El registro nuevo no apunta a id_precio_corregido 436.", {}
    if not _igual_decimal(nuevo.get("precio_unitario"), IMPORTE_CORRECCION):
        return "El importe persistido no es 4200000.00.", {}
    if nuevo.get("fecha_vigencia") != VIGENCIA_ORIGINAL:
        return "La corrección no heredó la vigencia 2026-11-01 del 436.", {}
    if nuevo.get("fecha_vencimiento") is not None:
        return "La corrección no debe tener fecha de vencimiento.", {}
    if nuevo.get("estado") != "SUPERADO" or bool(nuevo.get("es_aplicado")):
        return "La corrección histórica no quedó SUPERADO / no aplicada.", {}
    if original is None or original.get("estado") != "CORREGIDO" or bool(original.get("es_aplicado")):
        return "El precio 436 no quedó CORREGIDO.", {}
    previo_436 = _fila(antes, CORREGIDO)
    if previo_436 is None or not almacenado_igual(previo_436, original):
        return "Los datos almacenados del 436 cambiaron (deben ser inmutables).", {}
    if aplicado is None or aplicado.get("estado") != "ACTIVO" or not bool(aplicado.get("es_aplicado")):
        return "El precio 645 no permaneció ACTIVO y aplicado.", {}
    previo_645 = _fila(antes, APLICADO)
    if previo_645 is None or not almacenado_igual(previo_645, aplicado):
        return "Los datos almacenados del 645 cambiaron.", {}
    ids_antes = {p.get("id_precio_mercado") for p in antes}
    ids_despues = {p.get("id_precio_mercado") for p in despues}
    if ids_despues != ids_antes | {nuevo_id}:
        return "El catálogo de la especie 424 ganó o perdió otro id.", {}
    for previo in antes:
        if previo["id_precio_mercado"] in {CORREGIDO, APLICADO}:
            continue
        actual = _fila(despues, previo["id_precio_mercado"])
        if actual is None or not almacenado_igual(previo, actual):
            return f"El precio {previo.get('id_precio_mercado')} cambió sus datos almacenados.", {}
        if actual.get("estado") != previo.get("estado") or bool(actual.get("es_aplicado")) is not bool(previo.get("es_aplicado")):
            return f"El estado leído del precio {previo.get('id_precio_mercado')} cambió.", {}
    return None, {
        "id_correccion": nuevo_id,
        "correccion": _resumen_precio(nuevo),
        "original": _resumen_precio(original),
        "aplicado": _resumen_precio(aplicado),
        "desviacion_pct_respuesta": respuesta.get("desviacion_pct"),
        "fecha_vigencia_respuesta": respuesta.get("fecha_vigencia"),
    }


def _ejecutar_funcional(cliente, token: str, carpeta: Path, peticiones: list, base: dict) -> int:
    escenarios: list[dict] = []
    ids_antes = {p.get("id_precio_mercado") for p in base["precios"]}

    # 1) Fuente distinta
    cuerpo_fuente = {
        "id_especie": ESPECIE,
        "categoria": CATEGORIA,
        "fuente": "UPRA",
        "precio_unitario": f"{IMPORTE_CORRECCION:.2f}",
        "evidencia_documental": "TC-M06-G106 negativo CORRECCION_NO_COINCIDE",
        "id_precio_corregido": CORREGIDO,
        "confirmar_desviacion": False,
    }
    r1 = _post(cliente, cuerpo_fuente, token, peticiones, "negativo_fuente")
    ok1 = (not r1["incierto"]) and r1["codigo"] == 400 and _codigo_error(r1["payload"]) == "CORRECCION_NO_COINCIDE"
    escenarios.append(_escenario(
        "negativo_fuente_distinta",
        "PASSED" if ok1 else ("BLOCKED" if r1["incierto"] else "FAILED"),
        {"http": 400, "error_code": "CORRECCION_NO_COINCIDE"},
        {"http": r1["codigo"], "error_code": _codigo_error(r1["payload"])},
        None if ok1 else "No se obtuvo CORRECCION_NO_COINCIDE.",
    ))

    # 2) Fecha distinta a la heredada
    cuerpo_fecha = {
        "id_especie": ESPECIE,
        "categoria": CATEGORIA,
        "fuente": FUENTE,
        "precio_unitario": f"{IMPORTE_CORRECCION:.2f}",
        "fecha_vigencia": VIGENCIA_APLICADO,
        "evidencia_documental": "TC-M06-G106 negativo FECHA_VIGENCIA_CORRECCION",
        "id_precio_corregido": CORREGIDO,
        "confirmar_desviacion": False,
    }
    r2 = _post(cliente, cuerpo_fecha, token, peticiones, "negativo_fecha")
    ok2 = (not r2["incierto"]) and r2["codigo"] == 400 and _codigo_error(r2["payload"]) == "FECHA_VIGENCIA_CORRECCION"
    escenarios.append(_escenario(
        "negativo_fecha_vigencia_distinta",
        "PASSED" if ok2 else ("BLOCKED" if r2["incierto"] else "FAILED"),
        {"http": 400, "error_code": "FECHA_VIGENCIA_CORRECCION"},
        {"http": r2["codigo"], "error_code": _codigo_error(r2["payload"])},
        None if ok2 else "No se obtuvo FECHA_VIGENCIA_CORRECCION.",
    ))

    codigo_chk, precios_chk = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones, "chequeo_pre_positivo")
    if codigo_chk != 200 or not isinstance(precios_chk, list):
        resumen = _armar_resumen("BLOQUEADO", False, base, escenarios, "No se pudo revalidar el catálogo antes del POSITIVO.")
        guardar(carpeta, "ultima", resumen, peticiones)
        return 2
    if {p.get("id_precio_mercado") for p in precios_chk} != ids_antes:
        resumen = _armar_resumen("BLOQUEADO", False, base, escenarios, "Los negativos alteraron el catálogo; se detiene el POSITIVO.")
        guardar(carpeta, "ultima", resumen, peticiones)
        return 2
    if not ok1 or not ok2:
        resumen = _armar_resumen("BLOQUEADO", False, base, escenarios, "Un negativo falló antes del escenario positivo.")
        guardar(carpeta, "ultima", resumen, peticiones)
        return 2

    # 3) Positivo
    confirmar = desviacion(IMPORTE_CORRECCION, IMPORTE_ORIGINAL) > base["umbral"]
    registro: list = []
    r3 = _post(cliente, _cuerpo_positivo(confirmar), token, peticiones, "positivo_correccion", registro)
    if r3["incierto"]:
        _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones, "post_incierto")
        escenarios.append(_escenario(
            "positivo_correccion_historica", "BLOCKED",
            {"http": 201, "436": "CORREGIDO", "correccion": "SUPERADO", "645": "ACTIVO"},
            {"http": r3["codigo"], "error_code": _codigo_error(r3["payload"])},
            "Respuesta del POST positiva incierta; no se reintenta.",
        ))
        guardar(carpeta, "ultima", _armar_resumen("BLOQUEADO", False, base, escenarios, "POST positivo incierto."), peticiones)
        return 2

    codigo_despues, precios_despues = _get(
        cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones, "historial_post_positivo")
    detalle_pos = None
    evidencia_pos: dict = {}
    if r3["codigo"] == 201 and codigo_despues == 200 and isinstance(precios_despues, list):
        detalle_pos, evidencia_pos = _verificar_positivo(r3["payload"], base["precios"], precios_despues)
        ok3 = detalle_pos is None
    else:
        ok3 = False
        detalle_pos = f"HTTP {r3['codigo']} o GET posterior no utilizable."
    if r3["codigo"] == 409 and _codigo_error(r3["payload"]) == "DESVIACION_PRECIO_REQUIERE_CONFIRMACION" and not confirmar:
        # Solo un reintento autorizado por la regla del caso si el sistema lo exige.
        r3b = _post(
            cliente, _cuerpo_positivo(True), token, peticiones, "positivo_correccion_confirmada",
            registro, permitir_confirmacion=True,
        )
        codigo_despues, precios_despues = _get(
            cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones, "historial_post_confirmado")
        if r3b["codigo"] == 201 and codigo_despues == 200 and isinstance(precios_despues, list):
            detalle_pos, evidencia_pos = _verificar_positivo(r3b["payload"], base["precios"], precios_despues)
            ok3 = detalle_pos is None
            r3 = r3b
        else:
            ok3 = False
            detalle_pos = f"Tras confirmar desviación: HTTP {r3b.get('codigo')}."
    escenarios.append(_escenario(
        "positivo_correccion_historica",
        "PASSED" if ok3 else "FAILED",
        {
            "http": 201,
            "importe": "4200000.00",
            "fecha_vigencia_heredada": VIGENCIA_ORIGINAL,
            "desviacion_pct": "5",
            "436": "CORREGIDO",
            "correccion": "SUPERADO",
            "645": "ACTIVO_aplicado",
            "sin_vencimiento": True,
        },
        {
            "http": r3["codigo"],
            "error_code": _codigo_error(r3["payload"]),
            "verificacion": evidencia_pos,
        },
        detalle_pos,
    ))
    if not ok3:
        guardar(carpeta, "ultima", _armar_resumen("BLOQUEADO", False, base, escenarios, detalle_pos), peticiones)
        return 2

    # 4) Segunda corrección del 436
    r4 = _post(cliente, _cuerpo_positivo(False), token, peticiones, "negativo_ya_corregido")
    ok4 = (not r4["incierto"]) and r4["codigo"] == 409 and _codigo_error(r4["payload"]) == "PRECIO_YA_CORREGIDO"
    escenarios.append(_escenario(
        "negativo_precio_ya_corregido",
        "PASSED" if ok4 else ("BLOCKED" if r4["incierto"] else "FAILED"),
        {"http": 409, "error_code": "PRECIO_YA_CORREGIDO"},
        {"http": r4["codigo"], "error_code": _codigo_error(r4["payload"])},
        None if ok4 else "No se obtuvo PRECIO_YA_CORREGIDO.",
    ))

    codigo_final, precios_final = _get(
        cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones, "historial_final")
    historial = []
    if codigo_final == 200 and isinstance(precios_final, list):
        for precio in precios_final:
            if precio.get("categoria") == CATEGORIA and precio.get("fuente") == FUENTE:
                historial.append(_resumen_precio(precio))

    aprobado = all(e["estado"] == "PASSED" for e in escenarios)
    resumen = _armar_resumen(
        "APROBADO" if aprobado else "BLOQUEADO",
        aprobado,
        base,
        escenarios,
        None if aprobado else "Al menos un escenario no pasó.",
        historial=historial,
        id_correccion=(evidencia_pos or {}).get("id_correccion"),
    )
    guardar(carpeta, "ultima", resumen, peticiones)
    if aprobado:
        print("TC-M06-G106: 4/4 escenarios PASSED. Evidencia en resultados/ultima_evaluacion/.")
        return 0
    print("TC-M06-G106: hay escenarios FAILED o BLOCKED.", file=sys.stderr)
    return 2


def _armar_resumen(dictamen: str, aprobado: bool, base: dict | None, escenarios: list,
                   bloqueo: str | None, historial: list | None = None, id_correccion: int | None = None) -> dict:
    return {
        "caso": "TC-M06-G106",
        "subcaso": "TC-M06-30",
        "rf": ["RF-89"],
        "rf_version_referencia": "RF-89 v1.2 (RFC-026, aprobado 2026-11-11; comentario PR #1074)",
        "pr_referencia": "#1074",
        "ambiente": BASE_API,
        "fase": "ultima_evaluacion",
        "dictamen_general": dictamen,
        "caso_completo_aprobado": aprobado,
        "bloqueo": bloqueo,
        "reglas_aplicadas": {
            "hereda_fecha_vigencia": True,
            "desviacion_contra": "precio_corregido_436",
            "importe_correccion": f"{IMPORTE_CORRECCION:.2f}",
            "desviacion_esperada_pct": str(DESVIACION_ESPERADA),
            "sin_fecha_vencimiento": True,
            "estados_esperados": {"436": "CORREGIDO", "correccion": "SUPERADO", "645": "ACTIVO"},
        },
        "precondiciones": None if base is None else {
            "umbral": str(base["umbral"]),
            "original": _resumen_precio(base["original"]),
            "aplicado": _resumen_precio(base["aplicado"]),
            "desviacion_calculada": str(base["desviacion"]),
        },
        "id_correccion": id_correccion,
        "escenarios": escenarios,
        "historial_por_cabeza_mercado_activo": historial,
        "subcasos": [{
            "subcaso": "TC-M06-30",
            "estado": "APROBADO" if aprobado else "BLOQUEADO",
            "post_ejecutado": any(e["escenario"] == "positivo_correccion_historica" for e in escenarios),
            "motivo": bloqueo,
        }],
        "cierre_en": datetime.now(ZoneInfo(ZONA)).isoformat(),
    }


def correr(env: dict, cliente, hoy: date, carpeta: Path) -> int:
    del hoy  # la vigencia se hereda; no se elige fecha de negocio
    if env.get("TC_M06_G106_AUTORIZAR_SESION") != "AUTORIZADO":
        print("Falta TC_M06_G106_AUTORIZAR_SESION=AUTORIZADO.", file=sys.stderr)
        return 2
    modo = env.get("TC_M06_G106_MODO") or "DIAGNOSTICO"
    if modo not in {"DIAGNOSTICO", "FUNCIONAL"}:
        print("TC_M06_G106_MODO debe ser DIAGNOSTICO o FUNCIONAL.", file=sys.stderr)
        return 2
    if modo == "FUNCIONAL" and env.get("TC_M06_G106_AUTORIZAR_CORRECCION") != "AUTORIZADO":
        print("Falta TC_M06_G106_AUTORIZAR_CORRECCION=AUTORIZADO.", file=sys.stderr)
        return 2
    if not env.get("QA_CORREO") or not env.get("QA_CONTRASENA"):
        print("Faltan QA_CORREO y QA_CONTRASENA.", file=sys.stderr)
        return 2

    print("El inicio de sesión cierra cualquier otra sesión activa de la misma cuenta.", file=sys.stderr)
    peticiones: list = []
    try:
        codigo, login, _ = cliente.pedir(
            "POST", "/sesiones/",
            {"correo_electronico": env["QA_CORREO"], "contrasena": env["QA_CONTRASENA"]},
        )
    except ResultadoIncierto:
        print("La sesión no tuvo respuesta definitiva.", file=sys.stderr)
        return 2
    _registrar(peticiones, "POST", "/sesiones/", codigo, login if isinstance(login, dict) else {}, "sesion")
    token = login.get("token") if isinstance(login, dict) else None
    if codigo != 200 or not token:
        guardar(carpeta, "preparacion", _armar_resumen("BLOQUEADO", False, None, [], "No fue posible autenticar."), peticiones)
        return 2

    base, motivo = _leer_base(cliente, token, peticiones)
    if base is None:
        guardar(carpeta, "preparacion", _armar_resumen("BLOQUEADO", False, None, [], motivo), peticiones)
        print(motivo, file=sys.stderr)
        return 2

    if modo == "DIAGNOSTICO":
        resumen = _armar_resumen(
            "PENDIENTE_AUTORIZACION", False, base, [],
            "Diagnóstico OK. Precondiciones cumplidas. No se envió POST de corrección.",
        )
        resumen["fase"] = "preparacion"
        guardar(carpeta, "preparacion", resumen, peticiones)
        print("Diagnóstico listo. No se envió el POST positivo.")
        return 0

    return _ejecutar_funcional(cliente, token, carpeta, peticiones, base)


def main() -> int:
    return correr(dict(os.environ), ClienteUrllib(), hoy_bogota(), CARPETA)


if __name__ == "__main__":
    raise SystemExit(main())
