# | 2026-11-19 | Juan Sebastian Gutierrez | Generador de la colección Newman de TC-M08-G018 (RF-106) |
import json, sys

PRE_COLECCION = """// Cabeceras de sandbox y zona horaria en TODA petición (sandbox transaccional, X-Zona-Horaria del Swagger)
pm.request.headers.upsert({key: 'X-Test-Run-Id', value: pm.environment.get('run_id')});
pm.request.headers.upsert({key: 'X-Sandbox-Secret', value: pm.environment.get('sandbox_secret')});
pm.request.headers.upsert({key: 'X-Zona-Horaria', value: 'America/Bogota'});"""

# Utilidades que cada script de prueba necesita (Postman no comparte funciones entre scripts).
U = """const rid = pm.response.headers.get('X-Request-Id') || '-';
let b = {}; try { b = pm.response.json(); } catch (e) { b = {}; }
const ec = (b && b.error_code) ? b.error_code : '-';
const sinDatos = !(b && Object.prototype.hasOwnProperty.call(b, 'predicciones'));
function log(tipo, id, esperado, obtenido, estado) {
  console.log([tipo, id, 'esperado=' + esperado, 'obtenido=' + obtenido, 'estado=' + estado, 'req=' + rid].join('|'));
}
function cp(id, nombre, esperado, obtenidoFn, fn) {
  let ok = false;
  const obtenido = obtenidoFn();
  // El nombre de la aserción lleva el obtenido real para que quede en el reporte HTML y en la consola en una línea.
  pm.test(id + ' ' + nombre + ' || esperado: ' + esperado + ' || obtenido: ' + obtenido + ' || req: ' + rid, function () { fn(); ok = true; });
  log('CP', id, esperado, obtenido, ok ? 'OK' : 'FALLA');
}
function obs(id, texto) { log('OBS', id, '-', texto, 'OBSERVACION'); }
function bogota(iso) { return new Date(new Date(iso).getTime() - 5 * 3600 * 1000).toISOString().slice(0, 10); }
function snap(x) {
  const ids = (l, k) => (l || []).map(e => String(e[k])).sort();
  return JSON.stringify({
    metadatos: x.metadatos || null,
    predicciones: ids(x.predicciones, 'id_resultado_inferencia'),
    eventos: ids(x.eventos_sanitarios, 'id_evento'),
    retroalimentaciones: (x.retroalimentaciones || []).map(e => e.id_resultado_inferencia + ':' + e.valoracion + ':' + e.fecha).sort(),
    pendientes_total: x.pendientes ? x.pendientes.total : null,
    tvco: x.tvco ? x.tvco.porcentaje : null
  });
}
"""

def req(nombre, metodo, ruta, *, token="token_vet", body=None, query=None, pre=None, test=None):
    url = "{{base_url}}" + ruta
    if query:
        url += "?" + "&".join(f"{k}={v}" for k, v in query)
    headers = [{"key": "Content-Type", "value": "application/json"}]
    if token:
        headers.append({"key": "Authorization", "value": "Bearer {{" + token + "}}"})
    item = {"name": nombre, "request": {"method": metodo, "header": headers, "url": url}, "event": []}
    if body is not None:
        item["request"]["body"] = {"mode": "raw", "raw": body, "options": {"raw": {"language": "json"}}}
    if pre:
        item["event"].append({"listen": "prerequest", "script": {"type": "text/javascript", "exec": pre.split("\n")}})
    if test:
        item["event"].append({"listen": "test", "script": {"type": "text/javascript", "exec": (U + test).split("\n")}})
    return item

H = "/historial-predictivo/"
A = "{{id_activo_a}}"
ABORT = "postman.setNextRequest('Z99 Cierre del sandbox');"

items = [
 req("Z00 Login Veterinario", "POST", "/sesiones/", token=None,
     body='{"correo_electronico": "{{correo_vet}}", "contrasena": "{{contrasena_vet}}"}',
     pre="""// Fechas de calendario en Bogotá (UTC-5, sin horario de verano). Se calculan una vez por corrida.
const n = new Date(Date.now() - 5 * 3600 * 1000);
const y = n.getUTCFullYear(), m = n.getUTCMonth(), d = n.getUTCDate();
const f = (yy, mm, dd) => new Date(Date.UTC(yy, mm, dd)).toISOString().slice(0, 10);
pm.collectionVariables.set('hoy', f(y, m, d));
pm.collectionVariables.set('hace12m', f(y - 1, m, d));
pm.collectionVariables.set('hace24m', f(y - 2, m, d));
pm.collectionVariables.set('hace24m1d', f(y - 2, m, d - 1));
pm.collectionVariables.set('futuro30', f(y, m, d + 30));""",
     test="""if (pm.response.code === 200 && b.token) {
  pm.collectionVariables.set('token_vet', b.token);
  console.log('PRE|Z00|login Veterinario HTTP 200|req=' + rid);
  console.log('PRE|FECHAS|hoy=' + pm.collectionVariables.get('hoy') + ' hace12m=' + pm.collectionVariables.get('hace12m') +
    ' hace24m=' + pm.collectionVariables.get('hace24m') + ' hace24m1d=' + pm.collectionVariables.get('hace24m1d') +
    ' futuro30=' + pm.collectionVariables.get('futuro30'));
} else {
  console.log('ABORT|Z00|login Veterinario HTTP ' + pm.response.code + ' error_code=' + ec + '|req=' + rid);
  """ + ABORT + """
}"""),
 req("Z01 Perfil Veterinario", "GET", "/usuarios/me",
     test="""if (pm.response.code === 200 && b.nombre_rol === 'Veterinario') {
  console.log('PRE|Z01|id_usuario=' + b.id_usuario + ' nombre_rol=' + b.nombre_rol + '|req=' + rid);
} else {
  console.log('ABORT|Z01|perfil HTTP ' + pm.response.code + ' nombre_rol=' + (b.nombre_rol || '-') + '|req=' + rid);
  """ + ABORT + """
}"""),
 req("T00 Linea base historial", "GET", H + A,
     test="""const p = (b.predicciones || []).length, e = (b.eventos_sanitarios || []).length, r = (b.retroalimentaciones || []).length;
if (pm.response.code === 200 && p >= 1) {
  pm.collectionVariables.set('snap_t00', snap(b));
  console.log('PRE|T00|HTTP 200 predicciones=' + p + ' eventos=' + e + ' retroalimentaciones=' + r +
    ' pendientes=' + (b.pendientes ? b.pendientes.total : '-') + ' tvco=' + (b.tvco ? b.tvco.porcentaje : '-') +
    ' estado=' + (b.activo ? b.activo.estado : '-') + '|req=' + rid);
  obs('OBS-NOMBRES', 'claves=' + Object.keys(b).sort().join(',') + ' filtros_aplicados=' + ('filtros_aplicados' in b) +
    ' activo_seleccionado=' + ('activo_seleccionado' in b) + ' tvco_tipo=' + typeof b.tvco +
    ' metadatos=' + (b.metadatos ? Object.keys(b.metadatos).sort().join(',') : '-') +
    ' tvco_claves=' + (b.tvco && typeof b.tvco === 'object' ? Object.keys(b.tvco).sort().join(',') : '-'));
  obs('OBS-VENTANA', 'ventana_correspondencia_horas=' + b.ventana_correspondencia_horas);
  obs('OBS-DATOS', 'eventos_sanitarios=' + e + ' retroalimentaciones=' + r +
    ' (faltan los datos semilla de los puntos 2 y 9 del pedido al DBA si son 0; CP-11 compara igual el estado completo)');
  console.log('RETIRADO|CP-10|Activo dado de baja (RF-106 Precondicion 2): no hay activos dados de baja en las fincas del Veterinario (sonda 2026-11-19, punto 11 del pedido al DBA sin atender)|req=-');
  obs('OBS-TIMESTAMP', 'primera prediccion fecha=' + (b.predicciones[0] ? b.predicciones[0].fecha : '-'));
  obs('OBS-FUENTES', 'fuentes_no_disponibles=' + JSON.stringify(b.fuentes_no_disponibles));
} else {
  console.log('ABORT|T00|HTTP ' + pm.response.code + ' error_code=' + ec + ' predicciones=' + p + ' eventos=' + e +
    ' retroalimentaciones=' + r + ' (el activo A necesita al menos una prediccion)|req=' + rid);
  """ + ABORT + """
}"""),
 req("T00a Linea base auditoria M04", "GET", "/prediccion/auditoria", query=[("pagina", "1"), ("por_pagina", "1")],
     test="""const primero = (b.items && b.items[0]) ? b.items[0].id_evento : '-';
pm.collectionVariables.set('aud_t00', pm.response.code + '|' + b.total + '|' + primero);
obs('OBS-AUD-T00', 'HTTP ' + pm.response.code + ' total=' + b.total + ' primer_id_evento=' + primero);"""),
 req("CP-01 Rango de 12 meses explicito", "GET", H + A,
     query=[("fecha_inicio", "{{hace12m}}"), ("fecha_fin", "{{hoy}}")],
     test="""const ini = pm.collectionVariables.get('hace12m'), fin = pm.collectionVariables.get('hoy');
const pred = b.predicciones || [];
const fuera = pred.filter(x => bogota(x.fecha) < ini || bogota(x.fecha) > fin);
cp('CP-01', '12 meses explicitos: 200 con los datos del rango (RF-106 Entradas; RF-67)',
  '200; rango_fechas_aplicado=' + ini + '..' + fin + '; >=1 prediccion y todas dentro del rango',
  () => 'HTTP ' + pm.response.code + ' rango=' + JSON.stringify(b.rango_fechas_aplicado) + ' predicciones=' + pred.length +
        ' fuera_de_rango=' + fuera.length + ' total_inferencias=' + (b.metadatos ? b.metadatos.total_inferencias : '-'),
  () => {
    pm.expect(pm.response.code).to.eql(200);
    pm.expect(b.rango_fechas_aplicado).to.eql({fecha_inicio: ini, fecha_fin: fin});
    pm.expect(pred.length).to.be.at.least(1);
    pm.expect(fuera.length).to.eql(0);
  });"""),
 req("CP-02 Inicio posterior al fin", "GET", H + A,
     query=[("fecha_inicio", "2026-10-01"), ("fecha_fin", "2026-09-01")],
     test="""cp('CP-02', 'fecha_inicio > fecha_fin: 400 sin datos (RF-67 E3; openapi de TEST)', '400 sin datos',
  () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect(pm.response.code).to.eql(400); pm.expect(sinDatos).to.eql(true); });
obs('OBS-TEXTO-CP02', 'message=' + (b.message || '-'));"""),
 req("OBS-03 Fecha fin futura", "GET", H + A,
     query=[("fecha_inicio", "{{hace12m}}"), ("fecha_fin", "{{futuro30}}")],
     test="""obs('OBS-03', 'fecha_fin=hoy+30: HTTP ' + pm.response.code + ' error_code=' + ec + ' rango=' +
  JSON.stringify(b.rango_fechas_aplicado || null) + ' (RF-106 no define fechas futuras; RF-67 Integridad temporal es de otro endpoint)');"""),
 req("CP-04 Sin fechas", "GET", H + A,
     test="""const ini = pm.collectionVariables.get('hace12m'), fin = pm.collectionVariables.get('hoy');
cp('CP-04', 'Sin fechas: 200 con hoy - 12 meses a hoy (RF-106 Entradas; valores por defecto del Swagger)',
  '200; rango_fechas_aplicado=' + ini + '..' + fin,
  () => 'HTTP ' + pm.response.code + ' rango=' + JSON.stringify(b.rango_fechas_aplicado),
  () => { pm.expect(pm.response.code).to.eql(200); pm.expect(b.rango_fechas_aplicado).to.eql({fecha_inicio: ini, fecha_fin: fin}); });"""),
 req("CP-05 Activo inexistente", "GET", H + "999999",
     test="""cp('CP-05', 'Activo inexistente: 404 sin datos (RF-67 E2; Swagger: inexistente -> 404)', '404 sin datos',
  () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect(pm.response.code).to.eql(404); pm.expect(sinDatos).to.eql(true); });
obs('OBS-TEXTO-CP05', 'message=' + (b.message || '-'));"""),
 req("CP-06a Id no numerico", "GET", H + "abc",
     test="""cp('CP-06a', "id='abc': rechazo de validacion 400 o 422 sin datos (RF-106 Entradas; openapi publica 400 y 422)",
  '400 o 422 sin datos', () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect([400, 422]).to.include(pm.response.code); pm.expect(sinDatos).to.eql(true); });"""),
 req("CP-06b Id negativo", "GET", H + "-1",
     test="""cp('CP-06b', 'id=-1: rechazo 400, 404 o 422 sin datos (RF-106 Entradas; openapi publica 400, 404 y 422)',
  '400, 404 o 422 sin datos', () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect([400, 404, 422]).to.include(pm.response.code); pm.expect(sinDatos).to.eql(true); });"""),
 req("CP-07a Nivel de riesgo 4", "GET", H + A, query=[("nivel_riesgo", "4")],
     test="""cp('CP-07a', 'nivel_riesgo=4: rechazo 400 o 422 sin datos (RF-106 Entradas: 0 a 3; openapi publica 400 y 422)',
  '400 o 422 sin datos', () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect([400, 422]).to.include(pm.response.code); pm.expect(sinDatos).to.eql(true); });"""),
 req("CP-07b Nivel de riesgo -1", "GET", H + A, query=[("nivel_riesgo", "-1")],
     test="""cp('CP-07b', 'nivel_riesgo=-1: rechazo 400 o 422 sin datos (RF-106 Entradas: 0 a 3; openapi publica 400 y 422)',
  '400 o 422 sin datos', () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect([400, 422]).to.include(pm.response.code); pm.expect(sinDatos).to.eql(true); });"""),
 req("CP-08 Activo de finca no asignada", "GET", H + "{{id_activo_otra_finca}}",
     test="""cp('CP-08', 'Activo de una finca no asignada al Veterinario: 403 sin datos (Swagger: otra finca -> 403; RF-67 alcance)',
  '403 sin datos', () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos,
  () => { pm.expect(pm.response.code).to.eql(403); pm.expect(sinDatos).to.eql(true); });
obs('OBS-TEXTO-CP08', 'message=' + (b.message || '-'));"""),
 req("CP-09a Rango de 24 meses exactos", "GET", H + A,
     query=[("fecha_inicio", "{{hace24m}}"), ("fecha_fin", "{{hoy}}")],
     test="""const ini = pm.collectionVariables.get('hace24m'), fin = pm.collectionVariables.get('hoy');
cp('CP-09a', 'Rango de 24 meses exactos: 200 (RF-106 Restriccion 2)', '200; rango_fechas_aplicado=' + ini + '..' + fin,
  () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' rango=' + JSON.stringify(b.rango_fechas_aplicado || null),
  () => { pm.expect(pm.response.code).to.eql(200); pm.expect(b.rango_fechas_aplicado).to.eql({fecha_inicio: ini, fecha_fin: fin}); });"""),
 req("CP-09b Rango de 24 meses mas 1 dia", "GET", H + A,
     query=[("fecha_inicio", "{{hace24m1d}}"), ("fecha_fin", "{{hoy}}")],
     test="""cp('CP-09b', 'Rango de 24 meses + 1 dia: 400 sin datos (RF-106 Restriccion 2; Swagger: rango maximo de 24 meses -> 400)',
  '400 sin datos', () => 'HTTP ' + pm.response.code + ' error_code=' + ec + ' sin_datos=' + sinDatos +
  ' desde=' + pm.collectionVariables.get('hace24m1d'),
  () => { pm.expect(pm.response.code).to.eql(400); pm.expect(sinDatos).to.eql(true); });"""),
 req("Z50 Login Productor", "POST", "/sesiones/", token=None,
     body='{"correo_electronico": "{{correo_productor}}", "contrasena": "{{contrasena_productor}}"}',
     test="""if (pm.response.code === 200 && b.token) { pm.collectionVariables.set('token_productor', b.token); }
obs('OBS-P-LOGIN', 'login Productor HTTP ' + pm.response.code);"""),
 req("OBS-P Historial con Productor", "GET", H + A, token="token_productor",
     test="""obs('OBS-P', 'Productor (TC-M08-048, observacion por API): HTTP ' + pm.response.code + ' error_code=' + ec +
  ' con_probabilidades=' + !sinDatos + ' (esperado por RF-106 Restriccion 1 y CA-6: 403)');"""),
 req("T99 Historial final", "GET", H + A,
     test="""const antes = pm.collectionVariables.get('snap_t00'), ahora = snap(b);
cp('CP-11', 'Solo lectura: el historial final es igual a la linea base (RF-106 Restriccion 3 y Postcondicion 3)',
  'HTTP 200 y mismo contenido que T00', () => 'HTTP ' + pm.response.code + ' iguales=' + (antes === ahora) + ' final=' + ahora,
  () => { pm.expect(pm.response.code).to.eql(200); pm.expect(JSON.parse(antes).predicciones.length).to.be.at.least(1);
          pm.expect(ahora).to.eql(antes); });"""),
 req("T99a Auditoria M04 final", "GET", "/prediccion/auditoria", query=[("pagina", "1"), ("por_pagina", "1")],
     test="""const primero = (b.items && b.items[0]) ? b.items[0].id_evento : '-';
obs('OBS-AUD-T99', 'antes=' + pm.collectionVariables.get('aud_t00') + ' despues=' + pm.response.code + '|' + b.total + '|' + primero +
  ' (RF-106 no exige auditar la consulta; RF-67 paso 7 es de otro endpoint)');"""),
 req("Z99 Cierre del sandbox", "DELETE", "/test-control/runs/{{run_id}}", token=None,
     test="""console.log('CIERRE|' + pm.response.code + '|' + (b.status || '-') + '|req=' + rid);"""),
]

def main():
    coleccion = {
     "info": {
      "name": "TC-M08-G018",
      "description": ("| 2026-11-19 | Juan Sebastian Gutierrez | Colección de TC-M08-G018 (TC-M08-047 y TC-M08-059, RF-106): "
                      "validaciones de GET /historial-predictivo y solo lectura. Diseño en evidencias/DISENO_TC-M08-G018.md |\n| 2026-11-19 | Juan Sebastian Gutierrez | v2 (ronda 1 parcial): T00 solo exige predicciones; CP-10 retirado por falta de un activo dado de baja en las fincas del Veterinario |"),
      "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
     },
     "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": PRE_COLECCION.split("\n")}}],
     "variable": [{"key": k, "value": ""} for k in
                  ["token_vet", "token_productor", "hoy", "hace12m", "hace24m", "hace24m1d", "futuro30", "snap_t00", "aud_t00"]],
     "item": items,
    }
    json.dump(coleccion, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(len(items), "peticiones;", sum(1 for i in items if i["name"].startswith("CP-") or i["name"].startswith("T99 ")), "con checkpoint")


if __name__ == "__main__":
    main()
