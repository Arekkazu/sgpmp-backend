# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G27 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G27 revisado contra la ficha: 120 verifica el precio manual justificado (con y sin justificación) y que la cosecha pendiente se reconozca; 121 verifica el ingreso manual de costos del producto; 122 y 123 y 124 verifican lo que pide la ficha o quedan BLOQUEADOS por función no implementada |
# | 2026-11-11 | Daniela Castillo | M06 RF-85 v1.2: 122, 123 y 124 reescritos con las reglas de conversión del sistema (masa a kg; volumen y unidades bloquean con aviso); 124b conserva «sin cantidad total» |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G27-V2.0.html; 122 exige el texto «Cantidad convertida: … = … kg» en la justificación del producto (#1011) |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
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
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G27/TC-M06-G27.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G27/reporte-TC-M06-G27-V2.0.html" --self-contained-html
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
    if not filas:
        # La operación de Desarrollo (#1010, POST /finanzas/productos/pendientes/{id_evento}/reconocimiento) es solo para costos de venta manuales (FA-2);
        # el precio manual de FA-1 se registra en RF-89 y la cosecha pendiente debe continuar. Se imprime el estado para el diagnóstico.
        lp = env.call("GET", RUTA_PENDIENTES, "contador")
        obs(f"con el precio manual registrado y la cola procesada no se reconoció el producto. Cola: {_estado_cola(env, ida)}")
        obs(f"GET {RUTA_PENDIENTES} tras registrar el precio: HTTP {lp.status} {str(lp.data)[:600]}")
    cola = _estado_cola(env, ida)
    assert filas, (f"con el precio manual justificado registrado la cosecha pendiente debía reconocerse y no se reconoció; estado de la cola de eventos: {cola}; "
                   f"eventos del activo: {env.tipos_auditoria(ida)}")
    esperado = trunc2(vn(200, PRECIO_MANUAL))
    assert dec(filas[-1]["valor_producto"]) == esperado, f"valor_producto esperado {esperado} (200 x {PRECIO_MANUAL} menos 6 %): {filas[-1]}"


def test_TC_M06_120d_diagnostico_precio_de_mercado_activo_retoma_la_cosecha_pendiente(env):
    """Diagnóstico de INC-M06-323 (FA-1), no es un caso de la ficha: separa «el precio ESTIMADA no se acepta» de «la cola no reintenta». Run propio:
    cosecha pendiente por falta de precio, se registra un precio de fuente MERCADO_ACTIVO (el de siempre) y se procesa la cola. Imprime si el evento se reintenta y si se reconoce."""
    env.nuevo_run()
    env.presupuesto(80)
    esc = env.escenario_producto("PRODUCCION", "20000.00", None)
    ida = env.activo_productivo(esc, "1000")
    env.prep(env.cosecha(ida, "200"), (200, 201), "evento productivo de 200 kg sin precio del producto")
    env.procesar_eventos()
    antes = _estado_cola(env, ida)
    assert not env.producto_sql(ida), "precondición: la cosecha debe estar pendiente (sin producto)"
    env.precio_producto(esc, ID_METRICA_PRODUCTIVA, PRECIO_MANUAL, desde=hoy() - timedelta(days=10))
    rp = env.procesar_eventos()
    despues = _estado_cola(env, ida)
    filas = env.producto_sql(ida)
    obs(f"cola antes del precio: {antes}")
    obs(f"procesar la cola tras registrar un precio MERCADO_ACTIVO: HTTP {rp.status} {(rp.text or '')[:300]}")
    obs(f"cola después: {despues}")
    obs(f"producto reconocido: {'sí, valor_producto ' + str(filas[-1]['valor_producto']) if filas else 'no'}; eventos del activo: {env.tipos_auditoria(ida)}")
    lp = env.call("GET", RUTA_PENDIENTES, "contador")
    obs(f"GET {RUTA_PENDIENTES}: HTTP {lp.status} {str(lp.data)[:500]}")


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


RUTA_PENDIENTES = "/finanzas/productos/pendientes"


def _operacion_reconocer_pendiente(env):
    """INC-M06-323 (corregido por Desarrollo, #1010 / PR #1060): la cosecha pendiente se retoma con la operación
    POST /finanzas/productos/pendientes/{id_evento}/reconocimiento. El RF no trae rutas: se ubica en el OpenAPI de TEST y se imprime su esquema."""
    r = env.call("GET", "/openapi.json", sandbox=False)
    assert r.status == 200 and isinstance(r.data, dict), ("no se pudo leer /openapi.json para ubicar la operación que retoma la cosecha pendiente "
                                                         f"(INC-M06-323); respondió {r.status}. Pedirle a Desarrollo el endpoint y el cuerpo (PR #1060)")
    doc = r.data
    for ruta, ops in (doc.get("paths") or {}).items():
        if ruta.lower().startswith(RUTA_PENDIENTES + "/") and "reconocimiento" in ruta.lower() and "post" in ops:
            return doc, ruta, ops["post"]
    todas = _rutas_api(env, "producto", "pendiente", "cosecha", "costos-venta", "costos_venta")
    assert False, ("INC-M06-323: el OpenAPI de TEST no expone la operación que retoma la cosecha pendiente (Desarrollo la declaró corregida en #1010). "
                   f"Rutas parecidas: {todas}")


def _esquema_de(doc, op):
    def res(e):
        if isinstance(e, dict) and "$ref" in e:
            e = (doc.get("components", {}).get("schemas", {}) or {}).get(e["$ref"].split("/")[-1], {})
        return e if isinstance(e, dict) else {}
    esq = res((((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {})
    return esq, {k: res(v) for k, v in (esq.get("properties") or {}).items()}


def _cuerpo_reconocimiento(props, modo):
    """Arma el cuerpo con lo que declara el esquema: modo 'precio' (precio manual justificado) o 'costos' (costos de venta manuales)."""
    cuerpo = {}
    for k, e in props.items():
        kl = k.lower()
        if "justific" in kl:
            cuerpo[k] = JUSTIFICACION if modo == "precio" else "Costos de venta manuales del producto QA TC-M06 con soporte documental: cotización No. 777."
        elif modo == "precio" and "precio" in kl:
            cuerpo[k] = PRECIO_MANUAL
        elif modo == "costos" and kl in ("costos_manuales", "costos", "costos_venta", "costos_venta_producto"):
            cuerpo[k] = {"transporte": "1000", "comisiones": "1000", "impuestos": "1000", "otros": "0"}
        elif modo == "costos" and any(w in kl for w in ("transporte", "comision", "impuesto")):
            cuerpo[k] = "1000"
        elif modo == "costos" and "otros" in kl:
            cuerpo[k] = "0"
        elif any(w in kl for w in ("referencia", "evidencia", "soporte")):
            cuerpo[k] = "Cotización QA TC-M06 No. 101"
        elif kl.startswith("confirmar"):
            cuerpo[k] = True
    return cuerpo


def _id_evento_pendiente(env, ida):
    r = env.call("GET", RUTA_PENDIENTES, "contador")
    obs(f"GET {RUTA_PENDIENTES}: HTTP {r.status} {str(r.data)[:600]}")
    d = r.data
    items = d if isinstance(d, list) else ((d.get("pendientes") or d.get("items") or d.get("eventos") or d.get("data") or []) if isinstance(d, dict) else [])
    for it in items:
        if isinstance(it, dict) and str(it.get("id_activo_biologico")) == str(ida):
            ide = it.get("id_evento") or it.get("id_evento_productivo")
            if ide is not None:
                return ide
    pr = env.sql("SELECT p.id_evento AS e FROM modulo6.procesamientos_eventos_m02 p JOIN modulo2.eventos_activos ev ON ev.id_eventos = p.id_evento "
                 f"WHERE ev.id_activo_biologico = {int(ida)} AND p.resultado::text = 'MEDICION_PENDIENTE' ORDER BY p.id_evento DESC LIMIT 1")
    return uno(pr)


def _retomar_pendiente(env, ida, modo):
    doc, plantilla, op = _operacion_reconocer_pendiente(env)
    esq, props = _esquema_de(doc, op)
    obs(f"operación de Desarrollo: POST {plantilla} ({op.get('summary')}); campos: "
        f"{[(k, e.get('type'), k in (esq.get('required') or [])) for k, e in props.items()]}")
    ide = _id_evento_pendiente(env, ida)
    assert ide, f"no se encontró el evento pendiente del activo {ida} (cola: {_estado_cola(env, ida)})"
    cuerpo = _cuerpo_reconocimiento(props, modo)
    ruta = plantilla.replace("{id_evento}", str(ide))
    import re as _re
    for nombre in _re.findall(r"\{([^}]+)\}", ruta):
        ruta = ruta.replace("{" + nombre + "}", str(ide))
    r = env.call("POST", ruta, "contador", json=cuerpo)
    obs(f"POST {ruta} con {cuerpo}: HTTP {r.status} {(r.text or '')[:500]}")
    return r


def test_TC_M06_121b_costos_manuales_del_producto(env, sin_costos):
    """RF-85 FA-2 y ficha 121 (INC-M06-323, corregido por Desarrollo): con los costos de venta manuales del producto la cosecha pendiente continúa
    y el producto se reconoce."""
    esc, ida = sin_costos
    assert not env.producto_sql(ida), "precondición: la cosecha debe estar pendiente (sin producto)"
    r = _retomar_pendiente(env, ida, "costos")
    assert r.status in (200, 201, 202), f"los costos manuales del producto debían aceptarse y respondió {r}"
    env.procesar_eventos()
    filas = env.producto_sql(ida)
    assert filas, (f"con los costos manuales la cosecha pendiente debía continuar y reconocerse el producto; cola: {_estado_cola(env, ida)}; "
                   f"eventos del activo: {env.tipos_auditoria(ida)}")
    obs(f"producto reconocido con costos manuales: valor_producto {filas[-1]['valor_producto']}, precio {filas[-1]['precio_mercado_producto']}, costo_venta_producto {filas[-1]['costo_venta_producto']}")
    assert 0 < dec(filas[-1]["valor_producto"]) <= dec("700000"), f"valor_producto debía ser positivo y no superar el bruto 200 kg x 3.500,00: {filas[-1]}"


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
    fila_txt = str(uno(fila)).lower()
    assert "cantidad convertida" in fila_txt and f" {unidad.lower()} " in fila_txt and "kg" in fila_txt, (
        f"RF-85 v1.2 (#1011): la conversión debe quedar en la justificación del producto con el formato «Cantidad convertida: {cantidad} {unidad} = ... kg»: {str(uno(fila))[:600]}")


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
