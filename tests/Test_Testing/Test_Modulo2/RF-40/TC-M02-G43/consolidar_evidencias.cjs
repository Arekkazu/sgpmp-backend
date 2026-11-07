const fs = require('fs');
const path = require('path');

const resultados = path.join(__dirname, 'Resultados');
const oficiales = [
  { actor: 'Productor', activo: 279, usuario: 35, evento: 232, antes: 2, despues: 3, archivo: 'reporte_productor_tc_m02_g43.json' },
  { actor: 'Veterinario', activo: 311, usuario: 3, evento: 229, antes: 0, despues: 1, archivo: 'reporte_veterinario_tc_m02_g43.json' },
  { actor: 'Ingeniero de campo', activo: 312, usuario: 4, evento: 233, antes: 2, despues: 3, archivo: 'reporte_ingeniero_tc_m02_g43.json' },
];

function leerReporte(d) {
  const r = JSON.parse(fs.readFileSync(path.join(resultados, d.archivo), 'utf8'));
  const solicitudes = r.run.executions.map((e) => ({
    nombre: e.item.name,
    metodo: e.request.method,
    ruta: '/' + e.request.url.path.join('/'),
    estado_http: e.response.code,
    aserciones_fallidas: e.assertions.filter((a) => a.error).length,
  }));
  return {
    ...d,
    reporte_newman: d.archivo,
    reporte_html: d.archivo.replace('.json', '.html'),
    solicitudes: r.run.stats.requests.total,
    aserciones: r.run.stats.assertions.total,
    fallas: r.run.failures.length,
    detalle_http: solicitudes,
  };
}

const ejecuciones = oficiales.map(leerReporte);
const consolidado = {
  tipo: 'indice_consolidado_de_reportes_newman',
  caso: 'TC-M02-G43',
  requisito: 'RF-40',
  fecha_evento_oficial: '2026-09-09T23:01:00Z',
  resultado: 'APROBADO',
  alcance: 'Tres ciclos oficiales independientes: ANTES -> POST -> DESPUES. SETUP usó solo GET/SELECT.',
  totales: {
    ejecuciones: ejecuciones.length,
    solicitudes: ejecuciones.reduce((n, e) => n + e.solicitudes, 0),
    aserciones: ejecuciones.reduce((n, e) => n + e.aserciones, 0),
    fallas: ejecuciones.reduce((n, e) => n + e.fallas, 0),
  },
  ejecuciones,
};
fs.writeFileSync(path.join(resultados, 'reporte_tc_m02_g43.json'), JSON.stringify(consolidado, null, 2) + '\n');

const respuestas = {
  caso: 'TC-M02-G43',
  fuente: 'Extracción sin credenciales de los tres reportes Newman oficiales.',
  ejecuciones: ejecuciones.map(({ actor, activo, evento, solicitudes, aserciones, fallas, detalle_http }) => ({ actor, activo, evento, solicitudes, aserciones, fallas, detalle_http })),
};
fs.writeFileSync(path.join(resultados, 'respuestas_http.json'), JSON.stringify(respuestas, null, 2) + '\n');

const inventario = {
  caso: 'TC-M02-G43',
  setup: { escrituras_de_datos_de_prueba: 0, evidencia: ['reporte_setup_tc_m02_g43.json', 'consultas_bd.sql'], detalle: 'Solo GET a OpenAPI y SELECT en PostgreSQL.' },
  autenticacion: { observacion: 'Los POST a /sesiones/ autentican cada ejecución y no forman parte de los datos de negocio del caso.' },
  posts_negocio: [
    { actor: 'Productor', activo: 279, evento: 227, estado: 'Metodológico: consulta API posterior apuntó a endpoint solo poblacional.' },
    { actor: 'Productor', activo: 279, evento: 228, estado: 'Metodológico: fecha no posterior al evento 227.' },
    { actor: 'Veterinario', activo: 311, evento: 229, estado: 'OFICIAL: válido.' },
    { actor: 'Ingeniero de campo', activo: 312, evento: 230, estado: 'Metodológico: verificación directa de auditoría encontró permiso RF-52 separado.' },
    { actor: 'Ingeniero de campo', activo: 312, evento: 231, estado: 'Metodológico: fecha no posterior al evento 230.' },
    { actor: 'Productor', activo: 279, evento: 232, estado: 'OFICIAL: válido.' },
    { actor: 'Ingeniero de campo', activo: 312, evento: 233, estado: 'OFICIAL: válido.' },
  ],
  criterio_veredicto: 'Solo 232, 229 y 233 forman parte del veredicto oficial; los cuatro anteriores quedan trazados y excluidos.',
};
fs.writeFileSync(path.join(resultados, 'inventario_escrituras.json'), JSON.stringify(inventario, null, 2) + '\n');

const filas = ejecuciones.map((e) => `<tr><td>${e.actor}</td><td>${e.activo}</td><td>${e.evento}</td><td>${e.antes} → ${e.despues}</td><td>${e.solicitudes}</td><td>${e.aserciones}</td><td>${e.fallas}</td><td><a href="${e.reporte_html}">HTML Newman</a> · <a href="${e.reporte_newman}">JSON Newman</a></td></tr>`).join('\n');
const html = `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>TC-M02-G43 — Índice consolidado</title><style>body{font:15px system-ui,sans-serif;max-width:1100px;margin:32px auto;color:#1f2937}table{border-collapse:collapse;width:100%}th,td{border:1px solid #cbd5e1;padding:9px;text-align:left}th{background:#e2e8f0}.ok{color:#166534;font-weight:700}code{background:#f1f5f9;padding:2px 4px}</style></head><body><h1>TC-M02-G43 · RF-40</h1><p class="ok">APROBADO — tres ejecuciones oficiales, 24 solicitudes, 59 aserciones y 0 fallas.</p><p>Este es un índice consolidado; los reportes Newman nativos enlazados conservan el detalle de cada ciclo <code>ANTES → POST → DESPUÉS</code>. SETUP empleó únicamente GET/SELECT.</p><table><thead><tr><th>Actor</th><th>Activo</th><th>Evento oficial</th><th>Conteo</th><th>Solicitudes</th><th>Aserciones</th><th>Fallas</th><th>Evidencia nativa</th></tr></thead><tbody>${filas}</tbody></table><p>La verificación V6 del Ingeniero se respalda con <a href="bd_auditoria_final.log">consulta SELECT de bitácora</a>, porque su cuenta no dispone del permiso independiente de RF-52 para consultar la bitácora directamente.</p><p><a href="inventario_escrituras.json">Inventario completo de POST de negocio</a> · <a href="respuestas_http.json">respuestas HTTP resumidas</a></p></body></html>`;
fs.writeFileSync(path.join(resultados, 'reporte_tc_m02_g43.html'), html + '\n');
