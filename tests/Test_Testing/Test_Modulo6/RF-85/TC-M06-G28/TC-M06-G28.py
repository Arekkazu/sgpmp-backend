# | Fecha      | Nombre           | Que se hizo                                                              |
# |------------|------------------|--------------------------------------------------------------------------|
# | 2026-11-07 | Daniela Castillo | M06 RF-85: script del grupo TC-M06-G28 (pytest + sandbox, rol Contador) |
# | 2026-11-08 | Daniela Castillo | G28: PENDIENTE_RECONOCIMIENTO verifica sin producto ni asiento (FA-3 no lo cubre; rechazo de la ficha como observación) |
# | 2026-11-08 | Daniela Castillo | G28 revisado contra la ficha: 125 incluye el activo ACTIVO como control y exige rechazo con motivo; 126 prueba el período abierto y el cerrado; 127 verifica el cálculo conservado y la resolución al restaurar la matriz |
# | 2026-11-12 | Daniela Castillo | M06 reprueba V2.0 (RF-83 v1.2, RF-84 v1.1, RF-85 v1.2, RF-88 v2.0): el reporte HTML pasa a llamarse reporte-TC-M06-G28-V2.0.html |
# | 2026-11-13 | Daniela Castillo | M06 V2.0 (2.ª pasada): la base de datos pasa a ser la fuente de verdad (SQL ya funciona), expectativas alineadas con las correcciones de Desarrollo (notas de la versión 1.4.0) y las precondiciones que fallan ya no se omiten: quedan en rojo con diagnóstico |
"""
TC-M06-G28 - Elegibilidad del activo, período cerrado y falla del asiento en el reconocimiento del producto.   RF-85 (FA-3, FA-7, FA-9).   Casos: TC-M06-125 a TC-M06-127.

Precondición común (RF-43): el evento productivo de M02 exige una fase activa de un ciclo de M09; se usa la especie productiva sembrada de TEST (Cachama, métrica PESO en kg) y la fase se asigna
con POST /activos-biologicos/{id}/fases. Un producto no se registra dos veces el mismo día para un activo (409): cada caso usa su run y sus activos. Costos de venta de M09 del 6 %. Producto de PRODUCCION
con precio 3.500,00 por kg.
- 125: «solo el ACTIVO se reconoce; los demás se rechazan con motivo y sin asientos»: control ACTIVO (se reconoce) y INACTIVO y BAJA deben rechazarse con 4xx y un motivo, sin producto ni asiento (RF-85 FA-3). PENDIENTE_RECONOCIMIENTO (activo sin reconocimiento
  confirmado, sigue ACTIVO en M02) no está en FA-3: se exige solo que no haya producto ni asiento; el rechazo de la ficha queda como observación. COSECHADO_COMPLETAMENTE no existe en el catálogo de estados de M02 (ver G24 110c): se documenta.
- 126: dos activos del mismo período: la cosecha con el período abierto se reconoce con el período del evento (control) y, cerrado el período con RF-87, la cosecha del otro activo se bloquea. Los eventos llevan la fecha
  de hoy (M02 no admite fechas futuras ni anteriores al inicio del activo), por eso «último día del cerrado» y «primer día del abierto» se prueban con el cierre del período de hoy.
- 127: con la cuenta de PRODUCTO_AGRICOLA retirada de la matriz RF-109 (también la asignación general) el reconocimiento conserva el cálculo y la línea de asiento no se contabiliza. La ficha pide el estado
  PENDIENTE_CONFIRMACION, pero RF-86 v2.0 FA-5 y CA-21 mandan: la línea queda PENDIENTE_CUENTA con alerta y se resuelve al restaurar la matriz, sin recalcular (igual que G06 027, diferencia de la ficha).

Cómo correrlo:
    python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G28/TC-M06-G28.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G28/reporte-TC-M06-G28-V2.0.html" --self-contained-html
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

PRECIO_PRODUCTO = "3500.00"


def _escenario(env):
    return env.escenario_producto("PRODUCCION", "20000.00", PRECIO_PRODUCTO)


def test_TC_M06_125_estados_del_activo_solo_el_activo_se_reconoce(env):
    obs("COSECHADO_COMPLETAMENTE no existe en el catálogo de estados de M02 (ACTIVO, EN_TRATAMIENTO, INACTIVO, BAJA...): se cubre en G24 110c.")


@pytest.mark.parametrize("estado", ["ACTIVO", "INACTIVO", "BAJA", "PENDIENTE_RECONOCIMIENTO"])
def test_TC_M06_125_activo_segun_su_estado(env, estado):
    env.nuevo_run()
    env.presupuesto(80)
    esc = _escenario(env)
    if estado == "PENDIENTE_RECONOCIMIENTO":
        ida = env.activo(esc, origen="nacimiento", costo=None, soporte=None, peso_kg="1000")   # registrado y con fase, sin confirmar el reconocimiento
    else:
        ida = env.activo_productivo(esc, "1000")
    if estado == "INACTIVO":
        r = env.estado_activo(ida, "INACTIVO")
        if r.status not in (200, 201):
            bloqueado(f"M02 no permite pasar el activo a INACTIVO: {r}")
    elif estado == "BAJA":
        r = env.baja(ida, "perdida")
        if r.status not in (200, 201):
            bloqueado(f"M02 no permite dar de baja el activo: {r}")
    r = env.cosecha(ida, "100")
    obs(f"Evento productivo sobre activo {estado}: HTTP {r.status} {r.err} {(r.text or '')[:200]}")
    assert r.status < 500, f"{estado}: el evento productivo no debía dar 5xx: {r}"
    env.procesar_eventos()
    productos, lineas = env.producto_sql(ida), env.lineas_producto(ida)
    if estado == "ACTIVO":
        assert r.status in (200, 201), f"un activo ACTIVO debía aceptar la cosecha: {r}"
        assert productos, f"un activo ACTIVO debía reconocer el producto (eventos: {env.tipos_auditoria(ida)})"
        return
    fallos = []
    if estado == "PENDIENTE_RECONOCIMIENTO":
        # RF-85 FA-3 solo manda rechazar los activos dados de baja o INACTIVOS en M02; el activo sin reconocimiento confirmado sigue ACTIVO en M02 y M06 no lo reconoce (precondición de RF-85).
        # La ficha pide rechazo con motivo: diferencia de la ficha, se verifica lo que dicen el RF y el CU (sin producto ni asiento).
        obs(f"PENDIENTE_RECONOCIMIENTO: la ficha pide rechazo con motivo; RF-85 FA-3 solo cubre baja e INACTIVO. M02 aceptó el evento (HTTP {r.status}) y M06 no reconoció producto ni asiento. Eventos de auditoría: {env.tipos_auditoria(ida)}")
    elif not 400 <= r.status < 500:
        fallos.append(f"el evento sobre un activo {estado} debía rechazarse con motivo (4xx) y respondió {r}")
    elif not (r.text or "").strip():
        fallos.append(f"el rechazo debía traer el motivo y respondió {r}")
    if productos or lineas:
        fallos.append(f"un activo {estado} no debe reconocer producto ni asiento: {len(productos)} producto(s), {len(lineas)} línea(s)")
    assert not fallos, " | ".join(fallos)


def test_TC_M06_126_periodo_abierto_se_reconoce_y_cerrado_se_bloquea(env):
    env.nuevo_run()
    env.presupuesto(120)
    esc = _escenario(env)
    ida_a = env.activo_productivo(esc, "1000")
    ida_b = env.activo_productivo(esc, "1000")
    periodo = env.periodo(ida_a)
    assert env.periodo(ida_b) == periodo, "los dos activos debían quedar en el mismo período"
    # Control: período abierto, se reconoce con el período del evento
    env.prep(env.cosecha(ida_a, "100"), (200, 201), "evento productivo con el período abierto")
    env.procesar_eventos()
    abierto = env.producto_sql(ida_a)
    assert abierto, f"con el período abierto la cosecha debía reconocerse (eventos: {env.tipos_auditoria(ida_a)})"
    assert int(abierto[-1]["id_periodo_contable"]) == int(periodo), f"el producto debía quedar en el período del evento ({periodo}): {abierto[-1]}"
    # Se cierra el período y se cosecha el otro activo
    c = env.cierre(periodo)
    if c.status not in (200, 201, 202):
        bloqueado(f"no se pudo cerrar el período {periodo}: {c}")
    estado = uno(env.sql(f"SELECT estado::text FROM modulo6.periodos_contables WHERE id_periodo_contable = {int(periodo)}"))
    if estado != "CERRADO":
        no_concluyente(f"el período quedó {estado}, no cerrado.")
    env.prep(env.cosecha(ida_b, "100"), (200, 201), "evento productivo con el período cerrado")
    env.procesar_eventos()
    cerrado = env.producto_sql(ida_b)
    nuevo = int(cerrado[-1]["id_periodo_contable"]) if cerrado else None
    obs(f"Eventos del activo con la cosecha en período cerrado: {env.tipos_auditoria(ida_b)}")
    assert not cerrado, (f"la cosecha con el período cerrado debía bloquearse (RF-85 FA-7: no se permiten registros retroactivos) y se reconoció en el período {nuevo} "
                         f"(el cerrado era el {periodo}): {cerrado[-1]}")


def test_TC_M06_127_cuenta_de_la_matriz_retirada_conserva_el_calculo_y_deja_el_asiento_sin_contabilizar(env):
    env.nuevo_run()
    env.presupuesto(100)
    esc = _escenario(env)
    claves = [k for k in esc.asignaciones if k[0] == "PRODUCTO_AGRICOLA"]
    if not claves:
        no_verificable("la matriz de la especie no tiene cuentas de PRODUCTO_AGRICOLA propias que retirar.")
    ida = env.activo_productivo(esc, "1000")
    for clave in claves:
        env.prep(env.call("DELETE", f"/finanzas/configuracion/matriz/{esc.asignaciones[clave]}", "contador"), (200, 204), f"desactivar la cuenta {clave}")
    cfg = env.prep(env.call("GET", "/finanzas/configuracion", "contador"), (200,), "consultar la configuración contable")
    for a in (cfg.get("matriz") or []):
        if a.get("tipo_hecho") == "PRODUCTO_AGRICOLA" and a.get("id_especie") is None:
            env.prep(env.call("DELETE", f"/finanzas/configuracion/matriz/{a['id_asignacion_cuenta_contable']}", "contador"), (200, 204), "desactivar la asignación general")
    assert env.cosechar(ida, "200").status == 200
    productos = env.producto_sql(ida)
    assert productos, f"el reconocimiento debía conservar el cálculo aunque falte la cuenta (eventos: {env.tipos_auditoria(ida)})"
    p0 = productos[-1]
    lineas = env.lineas_producto(ida)
    assert not any(l["estado"] == "REGISTRADA" for l in lineas), f"sin cuenta configurada el asiento no debe contabilizarse: {lineas}"
    assert lineas and all(l["estado"] == "PENDIENTE_CUENTA" for l in lineas), f"la línea debía quedar PENDIENTE_CUENTA (RF-86 FA-5): {lineas}"
    assert "LINEA_ASIENTO_PENDIENTE_CUENTA" in env.tipos_auditoria(ida), "falta la alerta de línea pendiente de cuenta"
    obs("La ficha espera el estado PENDIENTE_CONFIRMACION; RF-86 v2.0 (FA-5 y CA-21) define PENDIENTE_CUENTA con alerta: se verifica RF-86 (diferencia de la ficha).")
    # Al restaurar la matriz se resuelve sin recalcular
    for clave in claves:
        deb, cre = esc.cuentas[clave]
        env.prep(env.call("POST", "/finanzas/configuracion/matriz", "contador", json={
            "tipo_hecho": clave[0], "sentido": clave[1], "id_especie": esc.id_especie, "cuenta_debito": deb, "cuenta_credito": cre}), (200, 201), f"restaurar la cuenta {clave}")
    lineas2 = env.lineas_producto(ida)
    assert lineas2 and all(l["estado"] == "REGISTRADA" for l in lineas2), f"al restaurar la matriz la línea debía quedar REGISTRADA: {lineas2}"
    p1 = env.producto_sql(ida)
    assert len(p1) == len(productos) and p1[-1]["id"] == p0["id"] and dec(p1[-1]["valor_producto"]) == dec(p0["valor_producto"]), f"el producto no debía recalcularse: antes {p0}, después {p1}"
