# | 2026-11-19 | Juan Sebastian Gutierrez | Generador de la sonda de datos de TC-M08-G018 (solo lectura, sin checkpoints) |
import json, sys
sys.path.insert(0, '.')
from gen_coleccion import PRE_COLECCION, req

U = """const rid = pm.response.headers.get('X-Request-Id') || '-';
let b = {}; try { b = pm.response.json(); } catch (e) { b = {}; }
const ec = (b && b.error_code) ? b.error_code : '-';
function s(clave, texto) { console.log('SONDA|' + clave + '|' + texto + '|req=' + rid); }
const PROHIBIDOS = [930, 900, 901, 825];
const VIGENTES = ['ACTIVO', 'EN_TRATAMIENTO'];
"""
ABORT = "postman.setNextRequest('S99 Cierre del sandbox');"

def r(nombre, metodo, ruta, **kw):
    it = req(nombre, metodo, ruta, **{k: v for k, v in kw.items() if k != 'test'})
    if 'test' in kw:
        it["event"].append({"listen": "test", "script": {"type": "text/javascript", "exec": (U + kw['test']).split("\n")}})
    return it

A = "{{id_activo_a}}"
items = [
 r("S00 Login Veterinario", "POST", "/sesiones/", token=None,
   body='{"correo_electronico": "{{correo_vet}}", "contrasena": "{{contrasena_vet}}"}',
   pre="""const n = new Date(Date.now() - 5 * 3600 * 1000);
const y = n.getUTCFullYear(), m = n.getUTCMonth(), d = n.getUTCDate();
const f = (yy, mm, dd) => new Date(Date.UTC(yy, mm, dd)).toISOString().slice(0, 10);
pm.collectionVariables.set('hoy', f(y, m, d));
pm.collectionVariables.set('hace12m', f(y - 1, m, d));
pm.collectionVariables.set('desde_iso', f(y - 1, m, d) + 'T05:00:00Z');
pm.collectionVariables.set('idx_finca', '0');
pm.collectionVariables.set('bajas', '[]');""",
   test="""if (pm.response.code === 200 && b.token) { pm.collectionVariables.set('token_vet', b.token); s('LOGIN_VET', 'HTTP 200'); }
else { console.log('ABORT|S00|login Veterinario HTTP ' + pm.response.code + ' error_code=' + ec + '|req=' + rid); """ + ABORT + """ }"""),
 r("S01 Perfil Veterinario", "GET", "/usuarios/me",
   test="""s('PERFIL_VET', 'HTTP ' + pm.response.code + ' id_usuario=' + b.id_usuario + ' nombre_rol=' + b.nombre_rol);
if (pm.response.code !== 200 || b.nombre_rol !== 'Veterinario') { console.log('ABORT|S01|rol=' + (b.nombre_rol || '-') + '|req=' + rid); """ + ABORT + """ }"""),
 r("S02 Fincas del Veterinario", "GET", "/reportes/opciones/finca",
   test="""const fincas = Array.isArray(b) ? b.map(x => Number(x.valor)) : [];
pm.collectionVariables.set('fincas_vet', JSON.stringify(fincas));
s('FINCAS_VET', 'HTTP ' + pm.response.code + ' fincas=' + JSON.stringify(Array.isArray(b) ? b.map(x => x.valor + ':' + x.etiqueta) : b));
if (fincas.length === 0) { console.log('ABORT|S02|el Veterinario no tiene fincas visibles|req=' + rid); """ + ABORT + """ }"""),
 r("S03 Historial predictivo del activo A", "GET", "/historial-predictivo/" + A,
   test="""s('A_HISTORIAL', 'HTTP ' + pm.response.code + ' error_code=' + ec + ' rango=' + JSON.stringify(b.rango_fechas_aplicado || null) +
  ' predicciones=' + (b.predicciones || []).length + ' eventos_sanitarios=' + (b.eventos_sanitarios || []).length +
  ' retroalimentaciones=' + (b.retroalimentaciones || []).length + ' pendientes=' + (b.pendientes ? b.pendientes.total : '-') +
  ' estado=' + (b.activo ? b.activo.estado : '-') + ' fuentes_no_disponibles=' + JSON.stringify(b.fuentes_no_disponibles || null));"""),
 r("S03b Historial del activo de otra finca", "GET", "/historial-predictivo/{{id_activo_otra_finca}}",
   test="""s('OTRA_FINCA_HISTORIAL', 'HTTP ' + pm.response.code + ' error_code=' + ec +
  ' con_datos=' + Object.prototype.hasOwnProperty.call(b, 'predicciones'));"""),
 r("S04 Ficha del activo A", "GET", "/activos-biologicos/" + A,
   test="""s('A_FICHA', 'HTTP ' + pm.response.code + ' identificador=' + b.identificador + ' nombre_estado=' + b.nombre_estado +
  ' id_finca=' + b.id_finca + ' id_especie=' + b.id_especie + ' tipo=' + b.tipo);"""),
 r("S05 Eventos M02 del activo A", "GET", "/activos-biologicos/" + A + "/eventos",
   test="""const ev = b.eventos || [];
const san = ev.filter(e => e.sanitario);
s('A_EVENTOS_M02', 'HTTP ' + pm.response.code + ' total=' + b.total + ' sanitarios=' + san.length +
  ' detalle=' + JSON.stringify(san.slice(0, 10).map(e => e.id_eventos + '@' + e.fecha)));"""),
 r("S06 Valoraciones M04 del activo A (bandeja)", "GET", "/prediccion/retroalimentacion/bandeja",
   query=[("id_activo_biologico", A), ("estado_evaluacion", "EVALUADO"), ("desde", "{{desde_iso}}"), ("por_pagina", "100")],
   test="""const it = b.items || [];
s('A_BANDEJA_EVALUADAS', 'HTTP ' + pm.response.code + ' error_code=' + ec + ' total=' + b.total +
  ' numero_evaluaciones=' + it.reduce((a, x) => a + (x.numero_evaluaciones || 0), 0) +
  ' detalle=' + JSON.stringify(it.slice(0, 10).map(x => String(x.id_resultado_inferencia).slice(0, 8) + ':' + x.numero_evaluaciones)));"""),
 r("S07 Historial RF-67 del activo A", "GET", "/prediccion/historial/" + A,
   query=[("fecha_inicio", "{{hace12m}}"), ("fecha_fin", "{{hoy}}")],
   test="""const tipos = {}; (b.eventos || []).forEach(e => { tipos[e.tipo_evento] = (tipos[e.tipo_evento] || 0) + 1; });
s('A_HISTORIAL_RF67', 'HTTP ' + pm.response.code + ' error_code=' + ec + ' total_pagina=' + b.total_pagina +
  ' hay_mas=' + !!b.cursor_siguiente + ' por_tipo=' + JSON.stringify(tipos));"""),
 r("S08 Activos por finca del Veterinario", "GET", "/activos-biologicos",
   query=[("id_finca", "{{finca_actual}}"), ("page_size", "100"), ("pagina", "1")],
   pre="""const fincas = JSON.parse(pm.collectionVariables.get('fincas_vet') || '[]');
pm.collectionVariables.set('finca_actual', String(fincas[Number(pm.collectionVariables.get('idx_finca'))]));""",
   test="""const fincas = JSON.parse(pm.collectionVariables.get('fincas_vet'));
const i = Number(pm.collectionVariables.get('idx_finca'));
const reg = b.registros || [];
const noVig = reg.filter(a => !VIGENTES.includes(a.nombre_estado) && !PROHIBIDOS.includes(a.id_activo_biologico));
const bajas = JSON.parse(pm.collectionVariables.get('bajas')).concat(noVig.map(a => a.id_activo_biologico + ':' + a.nombre_estado + ':finca' + a.id_finca));
pm.collectionVariables.set('bajas', JSON.stringify(bajas));
s('FINCA_' + fincas[i], 'HTTP ' + pm.response.code + ' total_registros=' + b.total_registros + ' total_paginas=' + b.total_paginas +
  ' estados=' + JSON.stringify(reg.reduce((o, a) => { o[a.nombre_estado] = (o[a.nombre_estado] || 0) + 1; return o; }, {})) +
  ' no_vigentes=' + JSON.stringify(noVig.slice(0, 15).map(a => a.id_activo_biologico + ':' + a.nombre_estado)));
if (i + 1 < fincas.length) { pm.collectionVariables.set('idx_finca', String(i + 1)); postman.setNextRequest('S08 Activos por finca del Veterinario'); }
else { s('CANDIDATOS_BAJA', JSON.stringify(bajas.slice(0, 20))); }"""),
 r("S09 Login Productor", "POST", "/sesiones/", token=None,
   body='{"correo_electronico": "{{correo_productor}}", "contrasena": "{{contrasena_productor}}"}',
   test="""if (pm.response.code === 200 && b.token) { pm.collectionVariables.set('token_productor', b.token); }
s('LOGIN_PRODUCTOR', 'HTTP ' + pm.response.code);
if (pm.response.code !== 200) { postman.setNextRequest('S99 Cierre del sandbox'); }"""),
 r("S10 Activos del Productor", "GET", "/activos-biologicos", token="token_productor",
   query=[("page_size", "100"), ("pagina", "1")],
   test="""const fincasVet = JSON.parse(pm.collectionVariables.get('fincas_vet'));
const reg = b.registros || [];
const fuera = reg.filter(a => !fincasVet.includes(a.id_finca) && !PROHIBIDOS.includes(a.id_activo_biologico));
s('PRODUCTOR_ACTIVOS', 'HTTP ' + pm.response.code + ' total_registros=' + b.total_registros + ' total_paginas=' + b.total_paginas +
  ' fincas=' + JSON.stringify([...new Set(reg.map(a => a.id_finca))]));
s('CANDIDATOS_OTRA_FINCA', JSON.stringify(fuera.slice(0, 20).map(a => a.id_activo_biologico + ':' + a.nombre_estado + ':finca' + a.id_finca)));"""),
 r("S99 Cierre del sandbox", "DELETE", "/test-control/runs/{{run_id}}", token=None,
   test="""console.log('CIERRE|' + pm.response.code + '|' + (b.status || '-') + '|req=' + rid);"""),
]

col = {
 "info": {"name": "TC-M08-G018-sonda",
          "description": "| 2026-11-19 | Juan Sebastian Gutierrez | Sonda de solo lectura de TC-M08-G018: estado del activo A por fuente y candidatos para CP-08 y CP-10. Sin checkpoints. |\n| 2026-11-19 | Juan Sebastian Gutierrez | S03b: historial del activo de otra finca (403 esperado para CP-08) |",
          "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
 "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": PRE_COLECCION.split("\n")}}],
 "variable": [{"key": k, "value": ""} for k in ["token_vet", "token_productor", "hoy", "hace12m", "desde_iso",
                                                "fincas_vet", "idx_finca", "finca_actual", "bajas"]],
 "item": items,
}
json.dump(col, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(len(items), "peticiones")
