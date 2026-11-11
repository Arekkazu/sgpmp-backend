# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G27 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G27 revisado contra la ficha: 120 verifica el precio manual justificado (con y sin justificación) y que la cosecha pendiente se reconozca; 121 verifica el ingreso manual de costos del producto; 122 y 123 y 124 verifican lo que pide la ficha o quedan BLOQUEADOS por función no implementada |
# | 2026-11-11 | Daniela Castillo | M06 RF-85 v1.2: 122, 123 y 124 reescritos con las reglas de conversión del sistema (masa a kg; volumen y unidades bloquean con aviso); 124b conserva «sin cantidad total» |
"""
TC-M06-G27 - Precio, costos de venta y conversión de unidades del producto agrícola.   RF-85 (FA-1, FA-2, FA-8 de CU04).   Casos: TC-M06-120 a TC-M06-124.

Precondición (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09; se usa la especie productiva sembrada de TEST (Cachama, métrica PESO en kg) y la fase
se asigna con POST /activos-biologicos/{id}/fases. Un producto no se registra dos veces el mismo día para un activo (409): cada caso usa su run y su activo. Costos de venta de M09 del 6 %.
- 120: producto de PRODUCCION sin precio RF-89 del producto -> el reconocimiento queda pendiente con alerta (el RF la llama RECONOCIMIENTO_PENDIENTE; el backend, RECONOCIMIENTO_PRODUCTO_PENDIENTE).
  El «precio manual justificado» es un precio de fuente ESTIMADA de RF-89 (exige justificación de 50 caracteres como mínimo): sin justificación se rechaza (120b); con justificación se registra
  y la cosecha pendiente debe reconocerse con el valor calculado (120c): 200 kg x 3.500,00 menos 6 % = 658.000,00.
- 121: producto con precio pero sin costos de venta en M09 (el activo se reconoció con costos manuales) -> pendiente con alerta (121); el RF pide el ingreso manual de los costos del producto y que el
  proceso continúe (121b): se busca esa operación en la API; si no existe, queda BLOQUEADO por función no implementada.
- 122 (RF-85 v1.2, C24.4): reglas de conversión del sistema para cosechas de CONSUMO (masa a kg): g x 0,001, t x 1.000, lb x 0,45359237, arroba x 12,5. Se
  crea una métrica de la especie en la unidad de origen (M02 solo admite la unidad de la métrica), se cosecha en esa unidad sobre un activo de 1.000 kg y se
  verifica: producto reconocido con la cantidad y la unidad ORIGINALES, proporción cosechada = kg convertidos / 1.000 y el texto de la conversión en la justificación.
- 123: volumen (mL, L) no tiene regla de conversión: el reconocimiento se bloquea con aviso al Contador (mensaje de conversión), sin producto ni asiento.
- 124: unidades (unidad) no tiene regla de conversión: igual que 123. 124b: consumo sin cantidad total del activo (ausente y 0): el activo sin magnitud no se reconoce
  y, por tanto, no se calcula proporción; sin error 5xx (verificación previa, sin cambios).
- PRODUCCION no se convierte (RF-85 v1.2): no hay caso propio en este grupo.

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


def _cosecha_consumo_en(env, unidad, cantidad):
    """Run nuevo: activo de CONSUMO de 1.000 kg y una cosecha de `cantidad` en `unidad` (métrica propia de la especie en esa unidad)."""
    env.nuevo_run()
    env.presupuesto(100)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    # M09 solo admite por tipo: PESO g/kg/lb, VOLUMEN litros/l/ml, CONTEO unidades; cualquier otra (arroba, t) solo con tipo OTRO. M02 exige que el evento
    # use la unidad de la métrica y que la métrica esté habilitada en el ciclo activo.
    tipo = {"g": "PESO", "lb": "PESO", "mL": "VOLUMEN", "L": "VOLUMEN", "unidades": "CONTEO"}.get(unidad, "OTRO")
    idm = env.metrica(esc, f"Cosecha {unidad}", unidad, tipo=tipo, habilitar_ciclo=True)
    env.precio_producto(esc, idm, "1000.00", desde=hoy() - timedelta(days=10))
    ida = env.activo_productivo(esc, "1000")
    env.evento_productivo(ida, idm, cantidad, unidad)
    env.procesar_eventos()
    return esc, ida


def _texto_pendiente(env, ida):
    ev = [e for e in env.auditoria(ida) if e.get("tipo_evento") == "RECONOCIMIENTO_PRODUCTO_PENDIENTE"]
    return (str(ev[-1]) if ev else ""), env.tipos_auditoria(ida)


@pytest.mark.parametrize("unidad,cantidad,kg", [("g", "100000", "100"), ("lb", "1000", "453.59237"), ("arroba", "20", "250"), ("t", "0.3", "300")])
def test_TC_M06_122_conversion_de_masa_a_kg_con_las_reglas_del_sistema(env, unidad, cantidad, kg):
    esc, ida = _cosecha_consumo_en(env, unidad, cantidad)
    filas = env.producto_sql(ida)
    texto, tipos = _texto_pendiente(env, ida)
    assert filas, (f"la cosecha de {cantidad} {unidad} (= {kg} kg) debía reconocerse con la regla de conversión del sistema y no se reconoció; "
                   f"eventos del activo: {tipos}; aviso: {texto[:1200]}")
    p = filas[-1]
    assert dec(p["cantidad_cosechada"]) == dec(cantidad) and str(p["unidad_medida"]).lower() == unidad.lower(), (
        f"el producto debe conservar la cantidad y la unidad originales ({cantidad} {unidad}): {p}")
    esperada = dec(kg) / dec("1000")
    assert abs(dec(p["proporcion_cosechada"]) - esperada) <= dec("0.0001"), f"proporción esperada {esperada} ({kg} kg de 1.000 kg): {p}"
    fila = env.sql("SELECT r::text AS fila FROM modulo6.reconocimientos_productos_agricolas r "
                   f"WHERE id_activo_biologico = {int(ida)} ORDER BY id_reconocimiento_producto_agricola DESC LIMIT 1")
    obs(f"{cantidad} {unidad} -> {kg} kg; proporción {p['proporcion_cosechada']}; valor_producto {p['valor_producto']}")
    # El activo de 1.000 kg a 20.000,00 vale 18.800.000,00 neto (costos de M09 del 6 %): la reducción debe ser proporcional a los kg convertidos.
    esperada_red = dec("18800000") * dec(kg) / dec("1000")
    assert abs(dec(p["valor_reduccion_activo"]) - esperada_red) <= dec("0.01") + dec("18800000") * dec("0.0001"), (
        f"la reducción del activo debía ser proporcional a {kg} kg (≈ {esperada_red}): {p}")
    assert "convers" in str(uno(fila)).lower(), f"RF-85 v1.2: el texto de la conversión debe quedar en la justificación del producto: {str(uno(fila))[:400]}"


@pytest.mark.parametrize("unidad,cantidad", [("mL", "500000"), ("L", "500")])
def test_TC_M06_123_volumen_sin_regla_de_conversion_se_bloquea_con_aviso(env, unidad, cantidad):
    esc, ida = _cosecha_consumo_en(env, unidad, cantidad)
    texto, tipos = _texto_pendiente(env, ida)
    assert "RECONOCIMIENTO_PRODUCTO_PENDIENTE" in tipos, f"el volumen ({unidad}) no tiene regla: debía bloquearse con aviso al Contador (eventos: {tipos})"
    assert "conversi" in texto.lower(), f"el aviso debía indicar la falta de regla de conversión: {texto[:300]}"
    assert not env.producto_sql(ida) and not env.lineas_producto(ida), "sin regla de conversión no debe crearse producto ni asiento"


@pytest.mark.parametrize("unidad,cantidad", [("unidades", "10")])
def test_TC_M06_124_unidades_sin_regla_de_conversion_se_bloquea_con_aviso(env, unidad, cantidad):
    esc, ida = _cosecha_consumo_en(env, unidad, cantidad)
    texto, tipos = _texto_pendiente(env, ida)
    assert "RECONOCIMIENTO_PRODUCTO_PENDIENTE" in tipos, f"las unidades ({unidad}) no tienen regla: debía bloquearse con aviso al Contador (eventos: {tipos})"
    assert "conversi" in texto.lower(), f"el aviso debía indicar la falta de regla de conversión: {texto[:300]}"
    assert not env.producto_sql(ida) and not env.lineas_producto(ida), "sin regla de conversión no debe crearse producto ni asiento"


def test_TC_M06_124b_consumo_sin_cantidad_total_del_activo(env):
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
