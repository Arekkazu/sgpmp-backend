# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G30 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G30: 135b acepta diferencias menores a 0,01 (precisión 2 vs 4 decimales); 132a no exige id_activo en el historial del activo |
# | 2026-11-08 | Daniela Castillo | G30: 136 y 138 habilitan cada métrica en el ciclo productivo; 135 con precio de 2 decimales (RF-89); 132a revisa también el historial del activo |
# | 2026-11-08 | Daniela Castillo | G30 revisado: cada caso abre su run; 132 separa activo y período de tipo y rango (sin filtro: BLOQUEADO); 135 con cantidades de 3 decimales y verificación del activo; 136 con productos distintos el mismo día; 137 con el reconocimiento pendiente, el estado y el registro de los intentos; 138 con un activo y varias métricas |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G30-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 RF-85: 137 con Administrador con todos los permisos (líder y Análisis, 13-nov) y rol Auditor nuevo: se agrega el Auditor (403, 4 intentos registrados) y el Administrador no puede recibir 401/403
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G30 - Historial, inmutabilidad, idempotencia, exactitud, reducción acumulada, autorización y rendimiento del reconocimiento del producto.
RF-85.   Casos: TC-M06-132 a TC-M06-138.

Precondición común (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09; se usa la especie productiva sembrada de TEST (Cachama, métrica
PESO en kg) y la fase se asigna con POST /activos-biologicos/{id}/fases. Si M02 responde 5xx o rechaza, el caso queda BLOQUEADO. Un producto no se registra dos veces
el mismo día para un activo (409): cada cosecha usa un activo propio. Costos de venta de M09: 2 %+3 %+1 %.
- Newman: 137 (matriz de roles sobre el precio del producto) también está en TC-M06-G30.json (correr_newman.ps1 -Caso G30 -Modulo 6 -Rf RF-85); aquí 137 es más completo (parte de un reconocimiento pendiente, verifica que el estado no cambia
  y que cada intento queda registrado). 138 (tiempo <= 3 s) depende de la fase del activo (RF-37) y del evento productivo (RF-43), por eso se mide aquí con el responseTime de POST /finanzas/eventos/procesar.
- 132: 132a prueba los filtros que sí existen (activo: historial del activo; período: GET /finanzas/periodos/{id}/productos), con el total igual al SELECT y los campos de trazabilidad (RF-85 Salida 1); 132b prueba
  los filtros por tipo de producto y rango de valores de RNF-85-05: si la API no los trae queda BLOQUEADO (funcionalidad no implementada).
- 133: no existen PUT/PATCH/DELETE de productos: se intentan y se verifica que se rechazan y que el SELECT no cambia.
- 134: la cola se reprocesa 3 veces: un solo reconocimiento, una sola línea y el activo se reduce una vez (POST /finanzas/eventos/procesar no recibe id_evento: es la forma de entregar el mismo evento varias veces).
- 135: valor_producto = valor de la línea de inventario y valor_reduccion = reducción del activo (consumo); se repite con cantidades aleatorias de 3 decimales (el máximo de M02) mientras alcance el presupuesto. 135b compara además la
  reducción que queda en el valor neto del activo con el valor_reduccion del reconocimiento.
- 136: cosechas de 40 %, 40 % y 30 % del mismo activo el mismo día; RF-43 no admite repetir el mismo producto el mismo día, por eso cada cosecha lleva una métrica de producción distinta (kg). Si M02 rechaza la segunda, queda NO VERIFICABLE.
- 137: con un reconocimiento pendiente (cosecha sin precio del producto), el precio manual (POST /finanzas/precios) solo lo ingresa el Contador: sin token 401, Productor, Veterinario e Ingeniero de campo 403, el estado no cambia y cada intento queda registrado en la auditoría de M06 (igual que G07 036).
- 137: matriz de roles sobre el ingreso de precio del producto (POST /finanzas/precios). V2.0 (13-nov): Productor, Veterinario, Auditor (rol nuevo) e Ingeniero de campo 403; el Administrador tiene todos los permisos (no puede recibir 401/403).
- 138: tiempo de procesamiento de cada cosecha <= 3000 ms (lote acotado por el presupuesto del sandbox).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G30/TC-M06-G30.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G30/reporte-TC-M06-G30-V2.0.html" --self-contained-html
"""
from __future__ import annotations

import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from m06_lib import *  # noqa: F401,F403,E402
from m06_lib import _lista as lista_de  # noqa: E402

@pytest.fixture(scope="module")
def env():
    e = Entorno(("admin", "ingeniero", "productor", "veterinario", "auditor"))
    yield e
    e.cerrar()

_LOTE: list = []      # cosechas verificadas en 135, que 135b revisa contra el valor del activo


def _periodico(env, kg="200"):
    esc = env.escenario_producto("PRODUCCION", "20000.00", "3500.00")
    ida = env.activo_productivo(esc, "1000")
    r = env.cosechar(ida, kg)
    assert r.status == 200, r
    return esc, ida, r


def _metrica_producto(env, esc, nombre: str) -> int:
    """Métrica de producción (kg) nueva, habilitada en el ciclo productivo de la fase del activo (PUT /configuracion/metricas/{id}/ciclos-productivos)."""
    m = env.metrica(esc, nombre)
    env.prep(env.call("PUT", f"/configuracion/metricas/{m}/ciclos-productivos", "admin", json={"ids_ciclos_productivos": [ID_CICLO_PRODUCTIVO]}),
             (200, 201), "habilitar la métrica en el ciclo productivo (RF-43 E-04)")
    return m


def _auditoria_total(env) -> int:
    return int(uno(env.sql("SELECT count(*) AS n FROM modulo6.auditorias_financieras")) or 0)


def test_TC_M06_132a_historial_por_activo_y_por_periodo(env):
    env.nuevo_run()
    env.presupuesto(110)
    esc = env.escenario_producto("PRODUCCION", "20000.00", "3500.00")
    ida1, ida2 = env.activo_productivo(esc, "1000"), env.activo_productivo(esc, "1000")
    assert env.cosechar(ida1, "100").status == 200
    assert env.cosechar(ida2, "300").status == 200
    p1, p2 = env.producto_sql(ida1), env.producto_sql(ida2)
    if not p1 or not p2:
        no_verificable(f"no se reconocieron los dos productos (eventos: {env.tipos_auditoria(ida1)} / {env.tipos_auditoria(ida2)}).")
    periodo = p1[-1]["id_periodo_contable"]
    ids_periodo_bd = {int(f["id"]) for f in env.sql(f"SELECT id_reconocimiento_producto_agricola AS id FROM modulo6.reconocimientos_productos_agricolas WHERE id_periodo_contable = {int(periodo)}")}
    # por período
    r = env.call("GET", f"/finanzas/periodos/{periodo}/productos", "contador")
    assert r.status == 200, r
    lista = lista_de(r.data, "productos")
    assert {int(x.get("id_reconocimiento_producto_agricola")) for x in lista} == ids_periodo_bd, f"el listado del período trae {len(lista)} y la BD {len(ids_periodo_bd)}"
    otro = env.call("GET", f"/finanzas/periodos/{int(periodo) + 100000}/productos", "contador")
    assert otro.status in (200, 404) and not (otro.status == 200 and lista_de(otro.data, "productos")), f"un período sin productos no debe traer los de otro: {otro}"
    # por activo (historial del activo)
    filas_h1 = env.historial(ida1).get("productos") or []
    h1 = [int(x.get("id_reconocimiento_producto_agricola")) for x in filas_h1]
    assert h1 == [int(p1[-1]["id"])], f"el historial del activo debe traer solo sus productos: {h1} (esperado {[p1[-1]['id']]})"
    obs(f"Campos del historial del activo: {sorted(filas_h1[0].keys())}")
    # campos de trazabilidad (RF-85 Salida 1)
    fila = next(x for x in lista if int(x.get("id_reconocimiento_producto_agricola")) == int(p1[-1]["id"]))
    faltan = [k for k in ("id_evento_productivo", "id_activo_biologico", "fecha_cosecha") if fila.get(k) in (None, "")]
    obs(f"Campos del listado del período: {sorted(fila.keys())}")
    # INC-M06-325 (corregido por Desarrollo, #1012): el historial de productos agrícolas trae evento y usuario.
    assert any(k in fila for k in ("id_usuario", "usuario", "usuario_nombre")), (
        f"INC-M06-325: el listado del período debe traer el usuario que reconoció el producto; campos: {sorted(fila.keys())}")
    if not any(k in filas_h1[0] for k in ("id_usuario", "usuario", "usuario_nombre")):
        obs("El historial del propio activo no trae el usuario que reconoció el producto (RF-85 Salida 1 no lo pide; el listado del período sí lo trae): pregunta para Desarrollo.")
    faltan_h = [k for k in ("id_evento_productivo", "fecha_cosecha") if filas_h1[0].get(k) in (None, "")]      # el historial es del activo: no repite su id
    assert not faltan and not faltan_h, (f"las consultas de productos no traen los campos de trazabilidad que pide RF-85 Salida 1: el listado del período no trae {faltan} "
                                         f"y el historial del activo no trae {faltan_h}")


def test_TC_M06_132b_filtros_por_tipo_de_producto_y_rango_de_valores(env):
    """RNF-85-05 y ficha 132; INC-M06-325 (corregido por Desarrollo, #1012): el historial de productos filtra por tipo, rango de valor, evento y usuario."""
    env.nuevo_run()
    env.presupuesto(120)
    r = env.call("GET", "/openapi.json", sandbox=False)
    assert r.status == 200 and isinstance(r.data, dict), f"no se pudo leer /openapi.json de TEST ({r.status})"
    op = ((r.data.get("paths") or {}).get("/finanzas/periodos/{id_periodo_contable}/productos") or {}).get("get") or {}
    params = [x.get("name", "") for x in (op.get("parameters") or []) if x.get("in") == "query"]
    p_tipo = [x for x in params if "tipo" in x.lower()]
    p_min = [x for x in params if "min" in x.lower() or ("valor" in x.lower() and "desde" in x.lower())]
    p_max = [x for x in params if "max" in x.lower() or ("valor" in x.lower() and "hasta" in x.lower())]
    p_evt = [x for x in params if "evento" in x.lower()]
    p_usr = [x for x in params if "usuario" in x.lower()]
    p_act = [x for x in params if "activo" in x.lower()]
    assert p_tipo and p_min and p_max and p_act, (
        "INC-M06-325 / RNF-85-05: el listado de productos (GET /finanzas/periodos/{id}/productos) debía declarar filtros por activo, tipo de producto y rango de valor (mínimo y máximo); "
        f"parámetros declarados: {params or 'ninguno'}")
    esc = env.escenario_producto("PRODUCCION", "20000.00", "3500.00")
    ida1, ida2 = env.activo_productivo(esc, "1000"), env.activo_productivo(esc, "1000")
    assert env.cosechar(ida1, "100").status == 200
    assert env.cosechar(ida2, "300").status == 200
    p1, p2 = env.producto_sql(ida1), env.producto_sql(ida2)
    assert p1 and p2, f"no se reconocieron los dos productos (eventos: {env.tipos_auditoria(ida1)} / {env.tipos_auditoria(ida2)})"
    periodo = p1[-1]["id_periodo_contable"]
    id1, id2 = int(p1[-1]["id"]), int(p2[-1]["id"])
    v1, v2 = dec(p1[-1]["valor_producto"]), dec(p2[-1]["valor_producto"])
    assert v1 < v2, (v1, v2)

    def listar(**q):
        rr = env.call("GET", f"/finanzas/periodos/{periodo}/productos", "contador", params=q or None)
        assert rr.status == 200, f"{q}: {rr}"
        return {int(x.get("id_reconocimiento_producto_agricola")) for x in lista_de(rr.data, "productos")}

    assert {id1, id2} <= listar(), "sin filtros el listado debe traer los dos productos"
    assert {id1, id2} <= listar(**{p_tipo[0]: "PRODUCTO_PERIODICO"}), "el filtro por tipo PRODUCTO_PERIODICO debe traer los dos productos"
    assert not ({id1, id2} & listar(**{p_tipo[0]: "PRODUCTO_DE_CONSUMO"})), "el filtro por tipo PRODUCTO_DE_CONSUMO no debe traer productos periódicos"
    corte = str((v1 + v2) / 2)
    assert id2 in listar(**{p_min[0]: corte}) and id1 not in listar(**{p_min[0]: corte}), f"el filtro de valor mínimo {corte} debe traer solo el producto mayor"
    assert id1 in listar(**{p_max[0]: corte}) and id2 not in listar(**{p_max[0]: corte}), f"el filtro de valor máximo {corte} debe traer solo el producto menor"
    por_activo = listar(**{p_act[0]: ida1})
    assert id1 in por_activo and id2 not in por_activo, f"el filtro por activo {ida1} debe traer solo su producto: {por_activo}"
    # rangos inclusivos (ficha 132): el valor exacto del producto entra tanto como mínimo como máximo
    assert id1 in listar(**{p_min[0]: str(v1)}) and id2 in listar(**{p_min[0]: str(v2)}), "el valor mínimo debe ser inclusivo"
    assert id1 in listar(**{p_max[0]: str(v1)}) and id2 in listar(**{p_max[0]: str(v2)}), "el valor máximo debe ser inclusivo"
    # combinación de filtros (ficha 132): tipo + valor mínimo
    comb = listar(**{p_tipo[0]: "PRODUCTO_PERIODICO", p_min[0]: corte})
    assert id2 in comb and id1 not in comb, f"la combinación tipo + valor mínimo {corte} debe traer solo el producto mayor: {comb}"
    ev1 = p1[-1]["id_evento_productivo"]
    if p_evt:
        por_evento = listar(**{p_evt[0]: ev1})
        assert id1 in por_evento and id2 not in por_evento, f"el filtro por evento {ev1} debe traer solo su producto: {por_evento}"
    if p_usr:
        fila = next(x for x in lista_de(env.call("GET", f"/finanzas/periodos/{periodo}/productos", "contador").data, "productos")
                    if int(x.get("id_reconocimiento_producto_agricola")) == id1)
        uid = next((fila.get(k) for k in ("id_usuario", "usuario") if fila.get(k) is not None), None)
        assert uid is not None, f"el listado debe traer el usuario para poder filtrar por él: {sorted(fila)}"
        assert id1 in listar(**{p_usr[0]: uid}), f"el filtro por usuario {uid} debe traer su producto"
    obs(f"filtros probados: activo {p_act}, tipo {p_tipo}, mínimo {p_min}, máximo {p_max}, evento {p_evt or 'no declarado'}, usuario {p_usr or 'no declarado'}; "
        f"parámetros declarados: {params}.")


def test_TC_M06_133_el_reconocimiento_del_producto_es_inmutable(env):
    env.nuevo_run()
    env.presupuesto(80)
    esc, ida, _ = _periodico(env)
    antes = env.producto_sql(ida)
    if not antes:
        no_verificable(f"no se reconoció el producto (eventos: {env.tipos_auditoria(ida)}).")
    idp = antes[-1]["id"]
    for rol in ("contador", "admin"):
        for metodo, cuerpo in (("PATCH", {"valor_producto": "1.0000"}), ("PUT", {"valor_producto": "1.0000"}), ("DELETE", None)):
            r = env.call(metodo, f"/finanzas/productos/{idp}", rol, json=cuerpo)
            assert not (200 <= r.status < 300) and r.status < 500, f"{metodo} como {rol} no debe aceptarse y respondió {r}"
    assert env.producto_sql(ida) == antes, "los valores del reconocimiento deben permanecer intactos"


def test_TC_M06_134_idempotencia_del_reconocimiento(env):
    env.nuevo_run()
    env.presupuesto(80)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    ida = env.activo_productivo(esc, "1000")
    inicial = env.calculo(ida)
    assert env.cosechar(ida, "250").status == 200
    antes_p, antes_l, antes_c = env.producto_sql(ida), env.lineas_producto(ida), env.calculo(ida)
    if len(antes_p) != 1:
        no_verificable(f"se esperaba 1 reconocimiento y hay {len(antes_p)}.")
    for _ in range(3):
        assert env.procesar_eventos().status == 200
    assert env.producto_sql(ida) == antes_p and env.lineas_producto(ida) == antes_l, "el reproceso no debe duplicar reconocimiento ni asiento"
    assert env.calculo(ida) == antes_c, "el activo no debe reducirse otra vez"
    if inicial:
        reducido = dec(inicial["valor_neto"]) - dec(antes_c["valor_neto"])
        assert cerca(reducido, dec(antes_p[-1]["valor_reduccion_activo"]), "0.01"), f"el activo debe reducirse una sola vez ({reducido} vs {antes_p[-1]['valor_reduccion_activo']})"


def test_TC_M06_135_transferencia_exacta_a_inventario(env):
    _LOTE.clear()
    env.nuevo_run()
    env.presupuesto(150)
    azar = random.Random(20261108)
    esc = env.escenario_producto("CONSUMO", "3333.33")      # RF-89 solo admite 2 decimales en el precio (la ficha usa 4: ejemplo)
    while env.restante() > 35 and len(_LOTE) < 20:
        ida = env.activo_productivo(esc, "1000")
        antes = env.calculo(ida)
        kg = f"{azar.randint(10, 900)}.{azar.randint(0, 999):03d}"
        if env.cosechar(ida, kg).status != 200:
            break
        p, ls = env.producto_sql(ida), env.lineas_producto(ida)
        if not p or not ls:
            no_verificable(f"no se reconoció el producto de {kg} kg: {env.tipos_auditoria(ida)}")
        _LOTE.append((kg, antes, env.calculo(ida), p[-1], ls[-1]))
        assert dec(ls[-1]["valor"]) == dec(p[-1]["valor_producto"]) == dec(p[-1]["valor_reduccion_activo"]), (kg, ls[-1], p[-1])
    if len(_LOTE) < 3:
        no_concluyente(f"solo se verificaron {len(_LOTE)} reconocimientos dentro del presupuesto del sandbox.")
    obs(f"{len(_LOTE)} reconocimientos con cantidades de 3 decimales verificadas (la ficha pide 20; el run del sandbox dura 170 s).")


def test_TC_M06_135b_la_reduccion_del_activo_coincide_con_el_reconocimiento(env):
    if not _LOTE:
        no_verificable("depende de los reconocimientos que verifica 135 en esta misma corrida y 135 no dejó ninguno verificado (corra 135 y 135b juntos).")
    malos, maxima = [], dec("0")
    for kg, antes, despues, p, linea in _LOTE:
        if not antes or not despues:
            continue
        dif = dec(antes["valor_neto"]) - dec(despues["valor_neto"]) - dec(p["valor_reduccion_activo"])
        maxima = max(maxima, abs(dif))
        if abs(dif) >= dec("0.01"):       # el asiento y el reconocimiento se truncan a 2 decimales y el cálculo del activo guarda 4: una diferencia menor a 0,01 es precisión, no error
            malos.append(f"{kg} kg: neto {antes['valor_neto']} -> {despues['valor_neto']}, reducción {p['valor_reduccion_activo']}, diferencia {dif}")
    obs(f"Diferencia máxima entre la reducción del cálculo del activo (4 decimales) y el valor_reduccion del reconocimiento (2 decimales): {maxima}.")
    assert not malos, "la reducción del valor del activo no coincide con la del reconocimiento: " + " | ".join(malos[:5])


def test_TC_M06_136_reduccion_acumulada_coherente(env):
    env.nuevo_run()
    env.presupuesto(110)
    esc = env.escenario_producto("CONSUMO", "20000.00")
    ida = env.activo_productivo(esc, "1000")
    inicial = dec(env.calculo(ida)["valor_neto"])
    metricas = [ID_METRICA_PRODUCTIVA, _metrica_producto(env, esc, "Producto QA B"), _metrica_producto(env, esc, "Producto QA C")]
    respuestas = []
    for m, kg in zip(metricas, ("400", "400", "300")):
        r = env.call("POST", f"/activos-biologicos/{ida}/eventos/productivo", "admin", json={
            "id_metrica_produccion": m, "cantidad_producida": kg, "unidad_medida": "kg", "fecha_evento": str(hoy())})
        respuestas.append((kg, r.status))
        if r.status in (200, 201):
            env.procesar_eventos()
        elif kg != "300":
            no_verificable(f"M02 rechaza la cosecha de {kg} kg con un producto distinto el mismo día (HTTP {r.status} {r.err}): no se puede acumular 40 % + 40 % + 30 %.")
    productos = env.producto_sql(ida)
    reducciones = sum(dec(f["valor_reduccion_activo"]) for f in productos)
    final = dec(env.calculo(ida)["valor_neto"])
    obs(f"Cosechas {respuestas}; reconocimientos: {len(productos)}; reducciones {reducciones} de {inicial}; valor final del activo {final}.")
    assert reducciones <= inicial and final >= 0, f"el valor del activo no debe quedar negativo (reducciones {reducciones}, inicial {inicial}, final {final})"
    # INC-M06-326 (corregido por Desarrollo, #1013): la reducción del activo de consumo es acumulativa entre cosechas (40 % + 40 % = 80 % del valor inicial).
    tol = str(inicial * dec("0.000005"))                 # la proporción se guarda con 6 decimales (INC-M06-322): 400/600 = 0,666667
    assert cerca(reducciones, inicial * dec("0.8"), tol), f"INC-M06-326: las reducciones acumuladas debían sumar el 80 % del valor inicial ({inicial * dec('0.8')}) y suman {reducciones}"
    assert cerca(final, inicial * dec("0.2"), tol), f"INC-M06-326: el activo debía quedar con el 20 % de su valor inicial ({inicial * dec('0.2')}) y queda {final}"
    assert dec(env.calculo_bd(ida)["valor_neto"]) == final, "base de datos: el valor vigente del activo debe coincidir con la API"
    assert len(productos) == 2, (f"la tercera cosecha (110 % acumulado, supera la cantidad restante) debía rechazarse y hay {len(productos)} reconocimientos; "
                                 f"cantidades reconocidas: {[f['cantidad_cosechada'] for f in productos]}")


def test_TC_M06_137_ingreso_de_precio_del_producto_solo_el_contador(env):
    env.nuevo_run()
    env.presupuesto(100)
    esc = env.escenario_producto("PRODUCCION", "20000.00", None)        # sin precio del producto: la cosecha queda pendiente
    ida = env.activo_productivo(esc, "1000")
    env.prep(env.cosecha(ida, "200"), (200, 201), "evento productivo RF-43")
    env.procesar_eventos()
    if "RECONOCIMIENTO_PRODUCTO_PENDIENTE" not in env.tipos_auditoria(ida) or env.producto_sql(ida):
        no_verificable(f"el reconocimiento no quedó pendiente (eventos: {env.tipos_auditoria(ida)}).")
    cuerpo = {"id_especie": esc.id_especie, "categoria": "PRODUCTO", "id_metrica_produccion": ID_METRICA_PRODUCTIVA, "precio_unitario": "3000.00",
              "fecha_vigencia": str(hoy() - timedelta(days=1)), "fuente": "MERCADO_ACTIVO", "evidencia_documental": "QA TC-M06", "confirmar_desviacion": True}
    fallos = []
    antes = _auditoria_total(env)
    sin = env.call("POST", "/finanzas/precios", None, json=cuerpo)
    if sin.status != 401:
        fallos.append(f"sin token debía responder 401: {sin}")
    for rol in ("productor", "veterinario", "auditor"):
        r = env.call("POST", "/finanzas/precios", rol, json=cuerpo)
        if r.status != 403:
            fallos.append(f"{rol} no debe ingresar precios (403) y respondió {r}")
    env.set_rol(ROL_INGENIERO)
    try:
        r = env.call("POST", "/finanzas/precios", "ingeniero", json=cuerpo)
        if r.status != 403:
            fallos.append(f"Ingeniero de campo no debe ingresar precios (403) y respondió {r}")
    finally:
        env.contador()
    registrados = _auditoria_total(env) - antes
    if env.producto_sql(ida) or "RECONOCIMIENTO_PRODUCTO_PENDIENTE" not in env.tipos_auditoria(ida):
        fallos.append("el estado del reconocimiento pendiente cambió tras los intentos no autorizados")
    if registrados < 4:
        fallos.append(f"los intentos no autorizados (Productor, Veterinario, Auditor e Ingeniero de campo) no quedaron registrados en la auditoría de M06: {registrados} evento(s) nuevo(s) de 4 esperados")
    ok = env.call("POST", "/finanzas/precios", "contador", json=cuerpo)
    if ok.status not in (200, 201):
        fallos.append(f"el Contador sí debe poder ingresarlo: {ok}")
    a = env.call("POST", "/finanzas/precios", "admin", json={**cuerpo, "precio_unitario": "3100.00"})
    obs(f"Administrador registrando el precio del producto: HTTP {a.status}.")
    assert a.status not in (401, 403), f"el Administrador tiene todos los permisos (13-nov) y no debía recibir {a.status}: {a}"
    assert not fallos, " | ".join(fallos)


def test_TC_M06_138_tiempo_de_reconocimiento_del_producto(env):
    env.nuevo_run()
    env.presupuesto(150)
    esc = env.escenario_producto("PRODUCCION", "20000.00", "3500.00")
    tiempos = []
    # Un solo activo con una métrica de producción distinta por cosecha (el mismo producto no se registra dos veces el mismo día)
    ida = env.activo_productivo(esc, "1000")
    metricas = [ID_METRICA_PRODUCTIVA]
    while env.restante() > 30 and len(tiempos) < 20:
        if len(tiempos) < len(metricas):
            m = metricas[len(tiempos)]
        else:
            m = _metrica_producto(env, esc, f"Producto QA {len(tiempos)}")
            env.precio_producto(esc, m, "3500.00", desde=hoy() - timedelta(days=10))
            metricas.append(m)
        ev = env.call("POST", f"/activos-biologicos/{ida}/eventos/productivo", "admin", json={
            "id_metrica_produccion": m, "cantidad_producida": "10", "unidad_medida": "kg", "fecha_evento": str(hoy())})
        if ev.status not in (200, 201):
            if not tiempos:
                no_verificable(f"M02 rechaza el evento productivo (HTTP {ev.status} {ev.err}).")
            break
        r = env.procesar_eventos()
        assert r.status == 200, r
        tiempos.append(r.ms)
    if len(tiempos) < 5:
        no_concluyente(f"solo se midieron {len(tiempos)} reconocimientos dentro del presupuesto del sandbox.")
    obs(f"{len(tiempos)} reconocimientos secuenciales: máx {max(tiempos):.0f} ms, promedio {sum(tiempos) / len(tiempos):.0f} ms (la ficha pide 20).")
    assert max(tiempos) <= 3000, f"algún reconocimiento superó 3000 ms: {sorted(tiempos)[-3:]}"
