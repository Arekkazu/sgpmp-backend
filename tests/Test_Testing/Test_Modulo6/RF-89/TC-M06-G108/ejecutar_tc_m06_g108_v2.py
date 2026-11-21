# | Fecha      | Nombre | Que se hizo |
# |------------|--------|-------------|
# | 2026-11-10 | —      | Ejecutor vigente de TC-M06-G108. El diagnóstico no envía precios. |
"""TC-M06-G108 con la referencia vigente y el umbral leído.

Diagnóstico, sin POST de precios:
    TC_M06_G108_AUTORIZAR_SESION=AUTORIZADO
    TC_M06_G108_MODO=DIAGNOSTICO

Ejecución funcional, solo con las tres autorizaciones:
    TC_M06_G108_MODO=FUNCIONAL
    TC_M06_G108_AUTORIZAR_32=AUTORIZADO
    TC_M06_G108_AUTORIZAR_33=AUTORIZADO

No usa el ejecutor neutralizado ni su copia histórica.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from zoneinfo import ZoneInfo

CARPETA = Path(__file__).resolve().parent
BASE_API = "https://api.inmero.co/api-sgpmp-test"
ZONA = "America/Bogota"
ESPECIE = 424
CATEGORIA = "POR_CABEZA"
FUENTE = "MERCADO_ACTIVO"
CIEN = Decimal("100")
CENT = Decimal("0.01")
MARGEN = Decimal("12.5")
MAXIMO = Decimal("99999999.99")
EVIDENCIA_32 = "TC-M06-32 desviacion superior al umbral, sin confirmacion."
EVIDENCIA_33 = "TC-M06-33 desviacion exactamente igual al umbral, sin confirmacion."
CAMPOS_FILA = (
    "id_precio_mercado", "id_especie", "categoria", "fuente", "precio_unitario",
    "fecha_vigencia", "fecha_vencimiento", "id_metrica_produccion", "id_precio_corregido",
)
PROTEGIDOS = {
    "evidencia_peticiones_TC-M06-G108.json",
    "resultado_ejecucion_TC-M06-G108.html",
    "resumen_ejecucion_TC-M06-G108.json",
}
SECRETOS = {"token", "access_token", "contrasena", "password", "hash_integridad", "numero_id_tributaria"}


class ResultadoIncierto(Exception):
    """La petición no tuvo una respuesta HTTP definitiva. No se reintenta un POST."""


def hoy_bogota() -> date:
    return datetime.now(ZoneInfo(ZONA)).date()


def decimal(valor) -> Decimal:
    return Decimal(str(valor))


def desviacion(nuevo: Decimal, referencia: Decimal) -> Decimal:
    return abs(nuevo - referencia) / referencia * CIEN


def admisible(valor: Decimal) -> bool:
    return valor == valor.quantize(CENT) and Decimal("0") < valor <= MAXIMO


def importe_para(referencia: Decimal, porcentaje: Decimal) -> Decimal | None:
    bruto = referencia * (CIEN + porcentaje) / CIEN
    if not admisible(bruto) or desviacion(bruto, referencia) != porcentaje:
        return None
    return bruto.quantize(CENT)


def calcular(referencia: Decimal, umbral: Decimal) -> dict:
    exacto = importe_para(referencia, umbral)
    preferido = importe_para(referencia, umbral + MARGEN)
    if preferido is not None and desviacion(preferido, referencia) > umbral:
        superior, metodo = preferido, "margen_12_5"
    else:
        superior, metodo = _minimo_centavo(referencia, umbral)
    return {
        "exacto": exacto,
        "superior": superior,
        "metodo": metodo,
        "ejecutable": exacto is not None and superior is not None,
        "variacion_superior": None if superior is None else desviacion(superior, referencia),
        "variacion_exacta": None if exacto is None else desviacion(exacto, referencia),
    }


def _minimo_centavo(referencia: Decimal, umbral: Decimal) -> tuple[Decimal | None, str]:
    candidato = (referencia * (CIEN + umbral) / CIEN).quantize(CENT, rounding=ROUND_DOWN)
    if candidato < CENT:
        candidato = CENT
    for _ in range(3):
        if candidato > MAXIMO:
            break
        if admisible(candidato) and desviacion(candidato, referencia) > umbral:
            return candidato.quantize(CENT), "minimo_centavo"
        candidato += CENT
    return None, "no_ejecutable"


def _dia(valor) -> date:
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def seleccionar_referencia(precios: list[dict], hoy: date) -> tuple[dict | None, str]:
    """Misma regla que precio_vigente sobre una sola fuente. No retrocede si el último venció."""
    propios = []
    for precio in precios:
        if int(precio.get("id_especie") or 0) != ESPECIE:
            continue
        if precio.get("categoria") != CATEGORIA or precio.get("fuente") != FUENTE:
            continue
        if precio.get("id_metrica_produccion") not in (None, ""):
            continue
        propios.append(precio)
    iniciados = [p for p in propios if _dia(p["fecha_vigencia"]) <= hoy]
    if not iniciados:
        return None, "sin_precio_vigente"
    ultimo = max(iniciados, key=lambda p: (_dia(p["fecha_vigencia"]), int(p["id_precio_mercado"])))
    vencimiento = ultimo.get("fecha_vencimiento")
    if vencimiento not in (None, "") and _dia(vencimiento) < hoy:
        return None, "mas_reciente_vencido"
    return ultimo, "vigente"


def misma_referencia(izquierda: dict, derecha: dict) -> bool:
    return all(_normalizar(izquierda.get(campo)) == _normalizar(derecha.get(campo)) for campo in CAMPOS_FILA)


def _normalizar(valor):
    if valor in (None, ""):
        return None
    try:
        return format(decimal(valor).quantize(CENT), "f")
    except Exception:
        return valor


def leer_autorizacion(env: dict) -> dict:
    modo = env.get("TC_M06_G108_MODO") or "DIAGNOSTICO"
    return {
        "sesion": env.get("TC_M06_G108_AUTORIZAR_SESION") == "AUTORIZADO",
        "modo": modo,
        "subcaso_32": env.get("TC_M06_G108_AUTORIZAR_32") == "AUTORIZADO",
        "subcaso_33": env.get("TC_M06_G108_AUTORIZAR_33") == "AUTORIZADO",
    }


def puede_publicar_precios(autorizacion: dict) -> tuple[bool, str]:
    if autorizacion["modo"] != "FUNCIONAL":
        return False, "El modo no es FUNCIONAL."
    if not autorizacion["sesion"]:
        return False, "Falta la autorización de sesión."
    if not autorizacion["subcaso_32"]:
        return False, "Falta TC_M06_G108_AUTORIZAR_32=AUTORIZADO."
    if not autorizacion["subcaso_33"]:
        return False, "Falta TC_M06_G108_AUTORIZAR_33=AUTORIZADO."
    return True, "autorizado"


def umbral_de(configuracion: dict) -> Decimal | None:
    general = configuracion.get("general") if isinstance(configuracion, dict) else None
    if not isinstance(general, dict) or general.get("pct_umbral_desviacion_precio") is None:
        return None
    return decimal(general["pct_umbral_desviacion_precio"])


def especie_valida(catalogo: dict, configuracion: dict) -> tuple[bool, str]:
    items = catalogo.get("items") if isinstance(catalogo, dict) else None
    especie = next((item for item in items or [] if item.get("id_especie") == ESPECIE), None)
    if especie is None or not especie.get("es_activo"):
        return False, "La especie 424 no está activa en el catálogo."
    parametros = configuracion.get("especies") if isinstance(configuracion, dict) else None
    parametro = next((item for item in parametros or [] if item.get("id_especie") == ESPECIE), None)
    if parametro is None or parametro.get("categoria_precio") != CATEGORIA:
        return False, "La especie 424 no tiene categoría POR_CABEZA en la configuración financiera."
    return True, "valida"


def ruta_salida(carpeta: Path, fase: str, nombre: str) -> Path:
    if nombre in PROTEGIDOS:
        raise RuntimeError(f"Nombre reservado de la evaluación histórica: {nombre}")
    if fase not in {"preparacion", "ultima"}:
        raise RuntimeError("Fase de evidencia desconocida.")
    subcarpeta = "soporte_preparacion" if fase == "preparacion" else "ultima_evaluacion"
    destino = carpeta / "resultados" / subcarpeta / nombre
    if destino.resolve().parent == (carpeta / "resultados").resolve():
        raise RuntimeError("La evidencia nueva no se escribe en la raíz histórica.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    return destino


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
    if isinstance(valor, str) and len(valor) > 300:
        return valor[:300]
    return valor


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, indent=2, default=str)


def guardar(carpeta: Path, fase: str, resumen: dict, peticiones: list) -> None:
    prefijo = "preparacion" if fase == "preparacion" else "ejecucion_vigente"
    (ruta_salida(carpeta, fase, f"resumen_{prefijo}_TC-M06-G108.json")).write_text(_json(resumen), encoding="utf-8")
    (ruta_salida(carpeta, fase, f"evidencias_{prefijo}_TC-M06-G108.json")).write_text(
        _json({"caso": "TC-M06-G108", "fase": fase, "peticiones": limpiar(peticiones)}), encoding="utf-8")
    (ruta_salida(carpeta, fase, f"resultado_{prefijo}_TC-M06-G108.html")).write_text(_html(resumen), encoding="utf-8")


def _html(resumen: dict) -> str:
    return (
        "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"utf-8\"><title>TC-M06-G108</title></head><body>"
        f"<h1>TC-M06-G108 — {resumen.get('fase')}</h1>"
        f"<p>Dictamen: {resumen.get('dictamen_general')}. "
        f"Caso completo aprobado: {resumen.get('caso_completo_aprobado')}.</p>"
        f"<pre>{_json(resumen)}</pre></body></html>"
    )


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


def _registrar(peticiones: list, metodo: str, ruta: str, codigo, payload) -> None:
    peticiones.append({"metodo": metodo, "consulta": ruta, "codigo": codigo, "respuesta": limpiar(payload)})


def _get(cliente, ruta: str, token: str, peticiones: list):
    try:
        codigo, payload, _ = cliente.pedir("GET", ruta, token=token)
    except ResultadoIncierto:
        _registrar(peticiones, "GET", ruta, None, {"incierto": True})
        return None, None
    _registrar(peticiones, "GET", ruta, codigo, payload)
    return codigo, payload


def _post_unico(cliente, cuerpo: dict, token: str, registro: list, peticiones: list) -> dict:
    if registro:
        raise RuntimeError("Reenvío de POST prohibido.")
    registro.append(cuerpo["precio_unitario"])
    try:
        codigo, payload, _ = cliente.pedir("POST", "/finanzas/precios", cuerpo, token)
    except ResultadoIncierto as exc:
        _registrar(peticiones, "POST", "/finanzas/precios", None, {"incierto": True})
        return {"incierto": True, "codigo": None, "payload": None, "detalle": str(exc)}
    _registrar(peticiones, "POST", "/finanzas/precios", codigo, payload)
    return {"incierto": codigo is None or codigo >= 500, "codigo": codigo, "payload": payload, "detalle": None}


def _cuerpo(importe: Decimal, hoy: date, evidencia: str) -> dict:
    return {
        "id_especie": ESPECIE,
        "categoria": CATEGORIA,
        "fuente": FUENTE,
        "precio_unitario": format(importe, "f"),
        "fecha_vigencia": hoy.isoformat(),
        "evidencia_documental": evidencia,
        "confirmar_desviacion": False,
    }


def _fila(precios: list[dict], identificador: int) -> dict | None:
    return next((precio for precio in precios if precio.get("id_precio_mercado") == identificador), None)


def _eventos(cliente, token: str, tipo: str, peticiones: list) -> list:
    ruta = f"/finanzas/auditoria?tipo_evento={tipo}&formato=TECNICO&orden=DESC&tamano=500"
    codigo, payload = _get(cliente, ruta, token, peticiones)
    if codigo != 200 or not isinstance(payload, dict):
        return []
    return payload.get("eventos") or []


def _alta_ajena(eventos: list, ids_previos: set, importe: Decimal) -> bool:
    for evento in eventos:
        if evento.get("id_referencia") in ids_previos:
            continue
        payload = evento.get("payload_evento") or {}
        if payload.get("precio_unitario") is not None and decimal(payload["precio_unitario"]) == importe:
            return True
    return False


def _leer_base(cliente, token: str, hoy: date, peticiones: list) -> tuple[dict | None, str]:
    codigo_especies, especies = _get(cliente, "/configuracion/especies", token, peticiones)
    codigo_config, configuracion = _get(cliente, "/finanzas/configuracion", token, peticiones)
    codigo_precios, precios = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones)
    codigo_precios_2, precios_2 = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones)
    codigo_config_2, configuracion_2 = _get(cliente, "/finanzas/configuracion", token, peticiones)
    if not all(codigo == 200 for codigo in (codigo_especies, codigo_config, codigo_precios, codigo_precios_2, codigo_config_2)):
        return None, "Alguna lectura de preparación no respondió HTTP 200."
    if not isinstance(precios, list) or not isinstance(precios_2, list):
        return None, "El catálogo de precios no es una lista."
    valida, motivo = especie_valida(especies, configuracion)
    if not valida:
        return None, motivo
    umbral = umbral_de(configuracion)
    umbral_2 = umbral_de(configuracion_2)
    if umbral is None or umbral != umbral_2 or umbral <= 0:
        return None, "No se pudo confirmar el umbral efectivo."
    referencia, estado = seleccionar_referencia(precios, hoy)
    referencia_2, estado_2 = seleccionar_referencia(precios_2, hoy)
    if estado != "vigente" or estado_2 != "vigente" or not misma_referencia(referencia, referencia_2):
        return None, f"La referencia no quedó confirmada ({estado})."
    calculo = calcular(decimal(referencia["precio_unitario"]), umbral)
    return {
        "umbral": umbral,
        "referencia": referencia,
        "calculo": calculo,
        "precios": precios,
        "especies": especies,
    }, "listo"


def _resumen_base(fase: str, bloqueo: str | None, base: dict | None) -> dict:
    calculo = (base or {}).get("calculo") or {}
    referencia = (base or {}).get("referencia") or {}
    return {
        "caso": "TC-M06-G108",
        "fase": fase,
        "dictamen_general": "BLOQUEADO" if bloqueo or not calculo.get("ejecutable") else "PREPARADO",
        "caso_completo_aprobado": False,
        "post_precios": False,
        "bloqueo": bloqueo,
        "referencia": {
            "id_precio_mercado": referencia.get("id_precio_mercado"),
            "precio_unitario": referencia.get("precio_unitario"),
            "fecha_vigencia": referencia.get("fecha_vigencia"),
            "fecha_vencimiento": referencia.get("fecha_vencimiento"),
        },
        "umbral": None if base is None else str(base["umbral"]),
        "importe_superior": None if calculo.get("superior") is None else format(calculo["superior"], "f"),
        "importe_exacto": None if calculo.get("exacto") is None else format(calculo["exacto"], "f"),
        "metodo_superior": calculo.get("metodo"),
        "variacion_superior": None if calculo.get("variacion_superior") is None else str(calculo["variacion_superior"]),
        "subcasos": [
            {"subcaso": "TC-M06-32", "estado": "BLOQUEADO", "post_ejecutado": False},
            {"subcaso": "TC-M06-33", "estado": "BLOQUEADO", "post_ejecutado": False},
        ],
    }


def _verificar_32(respuesta: dict, antes: list[dict], despues, codigo_despues, referencia: dict, eventos: list, importe: Decimal) -> tuple[bool, str]:
    if respuesta["incierto"] or codigo_despues != 200 or not isinstance(despues, list):
        return False, "La respuesta de TC-M06-32 fue incierta o el catálogo posterior no se pudo leer. No se reenvió el POST."
    payload = respuesta["payload"] if isinstance(respuesta["payload"], dict) else {}
    if respuesta["codigo"] != 409 or payload.get("error_code") != "DESVIACION_PRECIO_REQUIERE_CONFIRMACION":
        return False, f"TC-M06-32 respondió {respuesta['codigo']}."
    ok, motivo = _catalogo_intacto(antes, despues, referencia)
    if not ok:
        return False, motivo
    if _alta_ajena(eventos, {p.get("id_precio_mercado") for p in antes}, importe):
        return False, "La auditoría muestra un alta del importe de TC-M06-32."
    return True, "HTTP 409 sin alta."


def _catalogo_intacto(antes: list[dict], despues: list[dict], referencia: dict) -> tuple[bool, str]:
    if {p.get("id_precio_mercado") for p in antes} != {p.get("id_precio_mercado") for p in despues}:
        return False, "El catálogo cambió de identificadores después del 409."
    actual = _fila(despues, referencia["id_precio_mercado"])
    if actual is None or not misma_referencia(referencia, actual):
        return False, "La referencia no conservó sus columnas."
    if actual.get("estado") != referencia.get("estado") or actual.get("es_aplicado") != referencia.get("es_aplicado"):
        return False, "El estado leído de la referencia cambió después del 409."
    return True, "referencia intacta"


def _verificar_33(respuesta: dict, precios: list[dict], referencia: dict, importe: Decimal, hoy: date, eventos_alta: list, eventos_reemplazo: list) -> tuple[bool, str, int | None]:
    if respuesta["incierto"]:
        return False, "La respuesta de TC-M06-33 fue incierta. No se reenvió el POST.", None
    payload = respuesta["payload"] if isinstance(respuesta["payload"], dict) else {}
    nuevo = payload.get("id_precio_mercado")
    if respuesta["codigo"] != 201 or not isinstance(nuevo, int):
        return False, f"TC-M06-33 respondió {respuesta['codigo']}.", None
    fila = _fila(precios, nuevo)
    if fila is None:
        return False, "El GET posterior no encontró el precio nuevo.", nuevo
    if any((
        int(fila.get("id_especie") or 0) != ESPECIE,
        fila.get("categoria") != CATEGORIA,
        fila.get("fuente") != FUENTE,
        decimal(fila.get("precio_unitario")) != importe,
        str(fila.get("fecha_vigencia"))[:10] != hoy.isoformat(),
        fila.get("es_aplicado") is not True,
    )):
        return False, "El precio nuevo no persistió con los datos enviados.", nuevo
    anterior = _fila(precios, referencia["id_precio_mercado"])
    if anterior is None or not misma_referencia(referencia, anterior):
        return False, "La fila anterior no conservó sus columnas.", nuevo
    if anterior.get("estado") != "SUPERADO" or anterior.get("es_aplicado") is not False:
        return False, "La lectura de la fila anterior no quedó SUPERADO y sin aplicación.", nuevo
    alta = next((e for e in eventos_alta if e.get("id_referencia") == nuevo), None)
    reemplazo = next((e for e in eventos_reemplazo if e.get("id_referencia") == nuevo), None)
    citado = (reemplazo or {}).get("payload_evento") or {}
    if alta is None or reemplazo is None or citado.get("id_precio_anterior") != referencia["id_precio_mercado"]:
        return False, "Falta la auditoría esperada del alta.", nuevo
    return True, "HTTP 201 verificado.", nuevo


def correr(env: dict | None = None, cliente=None, hoy: date | None = None, carpeta: Path | None = None) -> int:
    env = os.environ if env is None else env
    cliente = ClienteUrllib() if cliente is None else cliente
    hoy = hoy_bogota() if hoy is None else hoy
    carpeta = CARPETA if carpeta is None else carpeta
    autorizacion = leer_autorizacion(env)
    peticiones: list = []
    if not autorizacion["sesion"]:
        print("Falta TC_M06_G108_AUTORIZAR_SESION=AUTORIZADO. No se inicia sesión y no se envía ningún POST.", file=sys.stderr)
        return 2
    if autorizacion["modo"] not in {"DIAGNOSTICO", "FUNCIONAL"}:
        print("TC_M06_G108_MODO debe ser DIAGNOSTICO o FUNCIONAL.", file=sys.stderr)
        return 2
    permitido, motivo = puede_publicar_precios(autorizacion)
    if autorizacion["modo"] == "FUNCIONAL" and not permitido:
        print(motivo + " No se envía POST de precios.", file=sys.stderr)
        return 2
    if not env.get("QA_CORREO") or not env.get("QA_CONTRASENA"):
        print("Faltan QA_CORREO o QA_CONTRASENA. No se imprimen ni se inicia sesión.", file=sys.stderr)
        return 2
    print("AVISO: POST /sesiones/ puede invalidar otra sesión activa de la misma cuenta.", file=sys.stderr)
    try:
        codigo, login, _ = cliente.pedir(
            "POST", "/sesiones/",
            {"correo_electronico": env["QA_CORREO"], "contrasena": env["QA_CONTRASENA"]},
        )
    except ResultadoIncierto:
        print("El inicio de sesión no tuvo respuesta definitiva. No se reintenta.", file=sys.stderr)
        return 2
    _registrar(peticiones, "POST", "/sesiones/", codigo, login)
    token = login.get("token") if isinstance(login, dict) else None
    if codigo != 200 or not token:
        guardar(carpeta, "preparacion", _resumen_base("prevalidacion", "No fue posible autenticar al Contador.", None), peticiones)
        return 2
    base, estado = _leer_base(cliente, token, hoy, peticiones)
    resumen = _resumen_base("prevalidacion", None if estado == "listo" else estado, base)
    if estado != "listo" or not base["calculo"]["ejecutable"]:
        if estado == "listo":
            resumen["bloqueo"] = "El importe exacto o el superior no es admisible con esta referencia."
            resumen["dictamen_general"] = "BLOQUEADO"
        guardar(carpeta, "preparacion", resumen, peticiones)
        print(resumen["bloqueo"], file=sys.stderr)
        return 2
    guardar(carpeta, "preparacion", resumen, peticiones)
    print(
        f"Plan: referencia {resumen['referencia']['id_precio_mercado']} "
        f"importe {resumen['referencia']['precio_unitario']} umbral {resumen['umbral']} "
        f"superior {resumen['importe_superior']} ({resumen['metodo_superior']}) "
        f"exacto {resumen['importe_exacto']}.",
        file=sys.stderr,
    )
    if autorizacion["modo"] != "FUNCIONAL":
        print("Diagnóstico listo. No se envió POST /finanzas/precios.", file=sys.stderr)
        return 0
    return _ejecutar(cliente, token, hoy, carpeta, base, peticiones)


def _ejecutar(cliente, token: str, hoy: date, carpeta: Path, base: dict, peticiones: list) -> int:
    referencia = base["referencia"]
    calculo = base["calculo"]
    registro_32: list = []
    respuesta_32 = _post_unico(cliente, _cuerpo(calculo["superior"], hoy, EVIDENCIA_32), token, registro_32, peticiones)
    codigo_despues, precios_despues = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones)
    eventos_32 = _eventos(cliente, token, "PRECIO_REGISTRADO", peticiones)
    ok_32, motivo_32 = _verificar_32(
        respuesta_32, base["precios"], precios_despues, codigo_despues, referencia, eventos_32, calculo["superior"],
    )
    resumen = _resumen_base("ejecucion", None, base)
    resumen["post_precios"] = True
    resumen["subcasos"][0] = {
        "subcaso": "TC-M06-32", "estado": "APROBADO" if ok_32 else "BLOQUEADO",
        "post_ejecutado": True, "http": respuesta_32["codigo"], "motivo": motivo_32,
    }
    if not ok_32:
        resumen["dictamen_general"] = "BLOQUEADO"
        resumen["bloqueo"] = motivo_32
        guardar(carpeta, "ultima", resumen, peticiones)
        print(motivo_32, file=sys.stderr)
        return 2
    codigo_reval, precios_reval = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones)
    codigo_umbral, configuracion = _get(cliente, "/finanzas/configuracion", token, peticiones)
    precios_reval = precios_reval if isinstance(precios_reval, list) else []
    referencia_2, estado_2 = seleccionar_referencia(precios_reval, hoy) if codigo_reval == 200 else (None, "sin_lectura")
    umbral_2 = umbral_de(configuracion) if codigo_umbral == 200 else None
    if estado_2 != "vigente" or referencia_2 is None or not misma_referencia(referencia, referencia_2) or umbral_2 != base["umbral"]:
        resumen["dictamen_general"] = "BLOQUEADO"
        resumen["bloqueo"] = "La referencia o el umbral cambiaron antes de TC-M06-33. No se usa el importe anterior."
        resumen["subcasos"][1]["motivo"] = resumen["bloqueo"]
        guardar(carpeta, "ultima", resumen, peticiones)
        print(resumen["bloqueo"], file=sys.stderr)
        return 2
    recalculo = calcular(decimal(referencia_2["precio_unitario"]), umbral_2)
    if recalculo["exacto"] != calculo["exacto"] or not recalculo["ejecutable"]:
        resumen["dictamen_general"] = "BLOQUEADO"
        resumen["bloqueo"] = "El importe exacto dejó de ser admisible."
        guardar(carpeta, "ultima", resumen, peticiones)
        return 2
    registro_33: list = []
    respuesta_33 = _post_unico(cliente, _cuerpo(recalculo["exacto"], hoy, EVIDENCIA_33), token, registro_33, peticiones)
    codigo_final, precios_final = _get(cliente, f"/finanzas/precios?id_especie={ESPECIE}", token, peticiones)
    eventos_alta = _eventos(cliente, token, "PRECIO_REGISTRADO", peticiones)
    eventos_reemplazo = _eventos(cliente, token, "PRECIO_MARCADO_REEMPLAZADO", peticiones)
    ok_33, motivo_33, nuevo = _verificar_33(
        respuesta_33, precios_final if isinstance(precios_final, list) and codigo_final == 200 else [],
        referencia, recalculo["exacto"], hoy, eventos_alta, eventos_reemplazo,
    )
    resumen["subcasos"][1] = {
        "subcaso": "TC-M06-33", "estado": "APROBADO" if ok_33 else "BLOQUEADO",
        "post_ejecutado": True, "http": respuesta_33["codigo"], "id_precio_mercado": nuevo, "motivo": motivo_33,
    }
    resumen["caso_completo_aprobado"] = ok_33
    resumen["dictamen_general"] = "APROBADO" if ok_33 else "BLOQUEADO"
    resumen["bloqueo"] = None if ok_33 else motivo_33
    guardar(carpeta, "ultima", resumen, peticiones)
    print(motivo_33, file=sys.stderr)
    return 0 if ok_33 else 2


def main() -> int:
    return correr()


if __name__ == "__main__":
    raise SystemExit(main())
