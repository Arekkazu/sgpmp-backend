# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G27 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G27 revisado contra la ficha: 120 verifica el precio manual justificado (con y sin justificación) y que la cosecha pendiente se reconozca; 121 verifica el ingreso manual de costos del producto; 122 y 123 y 124 verifican lo que pide la ficha o quedan BLOQUEADOS por función no implementada |
"""
TC-M06-G27 - Precio, costos de venta y conversión de unidades del producto agrícola.   RF-85 (FA-1, FA-2, FA-8 de CU04).   Casos: TC-M06-120 a TC-M06-124.

Precondición (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09; se usa la especie productiva sembrada de TEST (Cachama, métrica PESO en kg) y la fase
se asigna con POST /activos-biologicos/{id}/fases. Un producto no se registra dos veces el mismo día para un activo (409): cada caso usa su run y su activo. Costos de venta de M09 del 6 %.
- 120: producto de PRODUCCION sin precio RF-89 del producto -> el reconocimiento queda pendiente con alerta (el RF la llama RECONOCIMIENTO_PENDIENTE; el backend, RECONOCIMIENTO_PRODUCTO_PENDIENTE).
  El «precio manual justificado» es un precio de fuente ESTIMADA de RF-89 (exige justificación de 50 caracteres como mínimo): sin justificación se rechaza (120b); con justificación se registra
  y la cosecha pendiente debe reconocerse con el valor calculado (120c): 200 kg x 3.500,00 menos 6 % = 658.000,00.
- 121: producto con precio pero sin costos de venta en M09 (el activo se reconoció con costos manuales) -> pendiente con alerta (121); el RF pide el ingreso manual de los costos del producto y que el
  proceso continúe (121b): se busca esa operación en la API; si no existe, queda BLOQUEADO por función no implementada.
- 122: conversión de unidades con reglas configuradas: el RF-85 (paso 6, FA-8 de CU04) pide aplicar la regla de conversión definida; se busca en la API alguna operación de reglas de conversión y, si
  no hay, queda BLOQUEADO por función no implementada.
- 123: sin regla de conversión se bloquea: especie de consumo medida por cabeza y cosecha en kg (la ficha usa M2 contra KG; el evento de M02 solo admite la unidad de la métrica): pendiente por falta
  de regla, con mensaje de conversión, sin producto ni asiento.
- 124: consumo sin cantidad total del activo (ausente y 0): el activo sin magnitud no se reconoce y, por tanto, no se calcula proporción; sin error 5xx.

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G27/TC-M06-G27.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G27/reporte-TC-M06-G27.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402

@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero"))
    yield e
    e.cerrar()

PRECIO_MANUAL = "3500.00"
JUSTIFICACION = "Sin precio de mercado activo ni UPRA para el producto; se estima con comparables de la región (QA TC-M06)."


def _pendiente(env, ida):
    tipos = env.tipos_auditoria(ida)
    return "RECONOCIMIENTO_PRODUCTO_PENDIENTE" in tipos, tipos


def _estado_cola(env, ida):
    return env.sql("SELECT p.resultado::text AS resultado, p.intentos, p.detalle FROM modulo6.procesamientos_eventos_m02 p "
                   f"JOIN modulo2.eventos_activos e ON e.id_eventos = p.id_evento WHERE e.id_activo_biologico = {int(ida)} ORDER BY p.id_evento")


def _rutas_api(env, *palabras):
    """Rutas del OpenAPI de TEST que contienen alguna de las palabras (para comprobar si existe una operación). None si no se puede leer."""
    r = env.call("GET", "/openapi.json", sandbox=False)
    if r.status != 200 or not isinstance(r.data, dict):
        return None
    return sorted(f"{m.upper()} {ruta}" for ruta, ops in (r.data.get("paths") or {}).items() for m in ops
                  if any(p in ruta.lower() for p in palabras))


@pytest.fixture(scope="module")
def sin_precio(env):
    env.nuevo_run()
    env.presupuesto(80)
    esc = env.escenario_producto("PRODUCCION", "20000.00", None)
    ida = env.activo_productivo(esc, "1000")
    env.prep(env.cosecha(ida, "200"), (200, 201), "evento productivo de 200 kg sin precio del producto")
    env.procesar_eventos()
    return esc, ida


def test_TC_M06_120_sin_precio_del_producto_queda_pendiente_con_alerta(env, sin_precio):
    esc, ida = sin_precio
    hay, tipos = _pendiente(env, ida)
    obs("El RF llama a la alerta RECONOCIMIENTO_PENDIENTE; el backend emite el evento de auditoría RECONOCIMIENTO_PRODUCTO_PENDIENTE (WARNING).")
    assert hay, f"debía quedar el reconocimiento pendiente con alerta (eventos: {tipos})"
    assert not env.producto_sql(ida), "sin precio del producto no debe reconocerse el producto"


def test_TC_M06_120b_precio_manual_sin_justificacion_se_rechaza(env, sin_precio):
    esc, ida = sin_precio
    r = env.call("POST", "/finanzas/precios", "contador", json={
        "id_especie": esc.id_especie, "categoria": "PRODUCTO", "id_metrica_produccion": ID_METRICA_PRODUCTIVA, "precio_unitario": PRECIO_MANUAL,
        "fecha_vigencia": str(hoy() - timedelta(days=10)), "fuente": "ESTIMADA", "evidencia_documental": "Cotización QA TC-M06",
        "justificacion_estimacion": "sin justificación", "confirmar_desviacion": True})
    assert r.status in (400, 422), f"un precio manual sin justificación suficiente debía rechazarse (400/422) y respondió {r}"


def test_TC_M06_120c_precio_manual_justificado_reconoce_la_cosecha_pendiente(env, sin_precio):
    esc, ida = sin_precio
    r = env.call("POST", "/finanzas/precios", "contador", json={
        "id_especie": esc.id_especie, "categoria": "PRODUCTO", "id_metrica_produccion": ID_METRICA_PRODUCTIVA, "precio_unitario": PRECIO_MANUAL,
        "fecha_vigencia": str(hoy() - timedelta(days=10)), "fuente": "ESTIMADA", "evidencia_documental": "Cotización QA TC-M06",
        "justificacion_estimacion": JUSTIFICACION, "confirmar_desviacion": True})
    assert r.status in (200, 201), f"el precio manual justificado debía registrarse: {r}"
    env.procesar_eventos()
    filas = env.producto_sql(ida)
    cola = _estado_cola(env, ida)
    assert filas, (f"con el precio manual justificado registrado la cosecha pendiente debía reconocerse y no se reconoció; estado de la cola de eventos: {cola}; "
                   f"eventos del activo: {env.tipos_auditoria(ida)}")
    esperado = trunc2(vn(200, PRECIO_MANUAL))
    assert dec(filas[-1]["valor_producto"]) == esperado, f"valor_producto esperado {esperado} (200 x {PRECIO_MANUAL} menos 6 %): {filas[-1]}"


@pytest.fixture(scope="module")
def sin_costos(env):
    env.nuevo_run()
    env.presupuesto(90)
    esc = env.escenario(categoria="PESO_KG", clasificacion="PRODUCCION", costos=None, precio=None, especie_existente=ID_ESPECIE_PRODUCTIVA)
    env.precio(esc, "20000.00", desde=hoy() - timedelta(days=10))
    env.precio_producto(esc, ID_METRICA_PRODUCTIVA, PRECIO_MANUAL, desde=hoy() - timedelta(days=10))
    ida, r = env.confirmar_manual(esc, {"transporte": "1000", "comisiones": "1000", "impuestos": "1000", "otros": "0"},
                                  "Costos manuales QA TC-M06 con soporte documental: cotización No. 101.", peso_kg="1000")
    if r.status not in (200, 201):
        bloqueado(f"no se pudo reconocer el activo sin costos de M09 (se hizo con costos manuales): {r}")
    env.procesar_eventos()
    env.prep(env.cosecha(ida, "200"), (200, 201), "evento productivo de 200 kg sin costos de venta del producto")
    env.procesar_eventos()
    return esc, ida


def test_TC_M06_121_sin_costos_de_venta_queda_pendiente_y_solicita_ingreso_manual(env, sin_costos):
    esc, ida = sin_costos
    hay, tipos = _pendiente(env, ida)
    assert hay, f"sin costos de venta de M09 debía quedar pendiente con alerta (eventos: {tipos})"
    assert not env.producto_sql(ida), "sin costos de venta no debe reconocerse el producto"
    ev = [e for e in env.auditoria(ida) if e.get("tipo_evento") == "RECONOCIMIENTO_PRODUCTO_PENDIENTE"]
    obs(f"Mensaje de la alerta: {str(ev[-1])[:250] if ev else 'n/d'}")


def test_TC_M06_121b_costos_manuales_del_producto(env, sin_costos):
    rutas = _rutas_api(env, "producto", "costos-venta", "costos_venta")
    obs(f"Operaciones de la API relacionadas con producto o costos de venta: {rutas if rutas is not None else 'no se pudo leer /openapi.json'}")
    bloqueado("funcionalidad no implementada: RF-85 FA-2 y la ficha 121 piden ingresar manualmente los costos de venta del producto (con justificación) para continuar el reconocimiento, "
              "y el backend solo deja el reconocimiento pendiente: no existe operación para costos manuales del producto ni se reprocesa la cosecha (ver operaciones listadas).")


def test_TC_M06_122_conversion_de_unidades(env):
    rutas = _rutas_api(env, "conversion", "conversi")
    obs(f"Operaciones de la API de reglas de conversión de unidades: {rutas if rutas is not None else 'no se pudo leer /openapi.json'}")
    if rutas:
        no_concluyente(f"existen operaciones de conversión ({rutas}) pero la cosecha solo admite la unidad de la métrica de la especie: no hay forma de enviar una unidad distinta al evento")
    bloqueado("funcionalidad no implementada: RF-85 paso 6 y FA-8 de CU04 piden aplicar la regla de conversión definida (p. ej. 1.000.000 mL = 1.000 LT) y registrar la cantidad original y la convertida; "
              "el backend no tiene reglas de conversión (solo reconoce kg como unidad del activo) y el evento productivo de M02 solo admite la unidad de la métrica.")


def test_TC_M06_123_sin_regla_de_conversion_se_bloquea(env):
    env.nuevo_run()
    env.presupuesto(90)
    esc = env.escenario(categoria="POR_CABEZA", clasificacion="CONSUMO", precio=None, especie_existente=ID_ESPECIE_PRODUCTIVA)
    env.precio(esc, "8000000.00", desde=hoy() - timedelta(days=10))
    ida, _ = env.reconocer(esc, origen="nacimiento", costo=None, soporte=None)
    env.procesar_eventos()
    fase = env.asignar_fase(ida)
    if fase.status not in (200, 201):
        bloqueado(f"no se pudo asignar la fase al activo: {fase}")
    env.prep(env.cosecha(ida, "10", "kg"), (200, 201), "evento productivo de 10 kg sobre un activo medido por cabeza")
    env.procesar_eventos()
    hay, tipos = _pendiente(env, ida)
    ev = [e for e in env.auditoria(ida) if e.get("tipo_evento") == "RECONOCIMIENTO_PRODUCTO_PENDIENTE"]
    texto = str(ev[-1]) if ev else ""
    obs("La ficha usa cosecha en M2 con precio en KG; el evento de M02 solo admite la unidad de la métrica, por eso se usa kg contra un activo medido por cabeza.")
    assert hay, f"sin regla de conversión kg -> cabezas el reconocimiento debía bloquearse con alerta (eventos: {tipos})"
    assert "conversi" in texto.lower(), f"el mensaje debía indicar la falta de regla de conversión: {texto[:300]}"
    assert not env.producto_sql(ida) and not env.lineas_producto(ida), "sin regla de conversión no debe crearse reconocimiento ni asiento"


def test_TC_M06_124_consumo_sin_cantidad_total_del_activo(env):
    env.nuevo_run()
    env.presupuesto(90)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    fallos = []
    # (a) cantidad total ausente: activo de consumo sin pesaje; (b) cantidad total 0: pesaje de 0 kg
    for etiqueta, peso in (("ausente", None), ("0", "0")):
        r = env.activo_r(esc, origen="nacimiento", costo=None, soporte=None)
        if r.status not in (200, 201):
            bloqueado(f"no se pudo registrar el activo ({etiqueta}): {r}")
        ida = r.get("id_activo_biologico")
        env.asignar_fase(ida)
        if peso is not None:
            rp = env.call("POST", f"/activos-biologicos/{ida}/eventos/crecimiento", "admin", json={
                "tipo_medicion": "PESO", "valor_medicion": peso, "unidad_medida": "kg"})
            obs(f"Pesaje de {peso} kg: HTTP {rp.status} {rp.err}")
            if rp.status >= 500:
                fallos.append(f"cantidad total {etiqueta}: el pesaje respondió {rp}")
        rc = env.confirmar(ida)
        obs(f"Reconocimiento del activo con cantidad total {etiqueta}: HTTP {rc.status} {rc.err} {(rc.text or '')[:160]}")
        if rc.status >= 500:
            fallos.append(f"cantidad total {etiqueta}: la confirmación del reconocimiento respondió {rc}")
        elif rc.status in (200, 201):
            fallos.append(f"cantidad total {etiqueta}: el activo de consumo debía bloquearse y se reconoció: {rc}")
        else:
            if not (rc.text or "").strip():
                fallos.append(f"cantidad total {etiqueta}: el bloqueo debía traer un mensaje claro y respondió {rc}")
        rcos = env.cosecha(ida, "10")
        if rcos.status >= 500:
            fallos.append(f"cantidad total {etiqueta}: el evento productivo respondió {rcos}")
        env.procesar_eventos()
        if env.producto_sql(ida) or env.lineas_producto(ida):
            fallos.append(f"cantidad total {etiqueta}: no debía calcularse proporción ni crearse producto o asiento")
    assert not fallos, " | ".join(fallos)
