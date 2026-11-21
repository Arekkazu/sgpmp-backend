import fs from 'node:fs';
import path from 'node:path';
import { CASOS } from './g92_escenario.mjs';
import { incidenciasProducto, incidenciasSandbox } from './g92_informe_incidencias.mjs';

// Texto de la fila G92 de Casos_Prueba(Modulo3 Agrupado).csv, sin cambiar el oráculo.
const CASO = {
  'TC-M03-181': {
    objetivo: 'Consolidar el estado general de una unidad utilizando el peor semáforo entre sus sensores.',
    esperado: 'El resumen de la unidad presenta ROJO como estado general (peor estado presente), incluyendo variables en atención/críticas, alertas activas asociadas y timestamp de actualización.',
  },
  'TC-M03-182': {
    objetivo: 'Consultar el monitoreo de una unidad productiva específica, mostrando solo su información.',
    esperado: 'El monitoreo muestra únicamente los sensores e información de la unidad seleccionada, sin datos de otras unidades.',
  },
  'TC-M03-183': {
    objetivo: 'Calcular el estado general de la unidad considerando todos sus sensores, no solo los de la página consultada.',
    esperado: 'En la página 1, estado_general="ROJO" aunque el sensor en ROJO no aparezca en el arreglo de sensores de esa página.',
  },
};

const REPORTE = 'newman/newman-TC-M03-G92.json';
const enlace = (archivo, nombre = archivo) => `[${nombre}](${archivo})`;
const valor = (x) => x == null ? 'NO CONSTA' : String(x).replaceAll('|', '\\|');
const http = (r, fase) => r.newman?.[0]?.fases?.find((x) => x.fase === fase)?.http ?? 'NO CONSTA';
const observado = (r, id) => r.casos?.[id]?.observado ?? {};
const estado = (r, id) => r.casos?.[id]?.veredicto ?? 'SIN VEREDICTO';

function detalleCaso(r, id) {
  const o = observado(r, id);
  const t = CASO[id];
  const runConciliado = r.run_id === 'RUN-G92-V1-20261031-022537';
  const filas = [];
  const agregar = (comprobacion, tipo, esperado, obtenido, fase) => {
    const x = r.casos?.[id]?.comprobaciones?.find((y) => y.id === comprobacion);
    if (!x) return;
    const evidencia = x.evidencia ?? 'resultado.json';
    filas.push({ comprobacion, tipo, esperado, obtenido, fase,
      estado: comprobacion === 'API-181-03' ? 'EXCLUIDA_DEL_ORACULO' : x.estado,
      evidencia });
  };
  let precondiciones, pasos, entradas, decision, falta;
  if (id === 'TC-M03-181') {
    const s = o.resumen_inicial ?? {};
    precondiciones = 'Unidad B (698), tres sensores 1202–1204 con lectura de 25 °C; alerta ESTRES_TERMICO CRITICO activa asociada a 1204. La matriz pide VERDE, AMARILLO y ROJO.';
    pasos = `Se ingresaron las tres lecturas y la alerta del escenario; se consultó GET /iot/monitoreo/dashboard filtrado por unidad B.${runConciliado ? ' Newman ejecutó además dos aserciones heredadas fuera del alcance QA vigente.' : ''}`;
    entradas = '`id_infraestructura=698&pagina=1&por_pagina=50`; sensores 1202, 1203 y 1204.';
    agregar('PRE-181-01', 'Precondición', 'Al menos un sensor VERDE y uno ROJO en B (decisión QA 2026-10-31)', '1202/1203 VERDE; 1204 ROJO; AMARILLO ausente', 'inicial');
    agregar('API-181-01', 'API', 'Estado general ROJO', `estado_general=${valor(s.estado_general)}; total ${valor(s.total_sensores)}`, 'inicial');
    agregar('API-181-02', 'API', 'Alerta activa asociada y timestamp', `alertas_activas_count=${valor(s.alertas_activas_count)}; asociada a 1204: ${o.alerta_critica_asociada === true ? 'sí' : 'no acreditado'}`, 'inicial');
    agregar('API-181-03', 'Observación', 'EXCLUIDA_DEL_ORACULO por decisión QA 2026-10-25; registrar variables visibles', `variable crítica Temperatura Ambiental en sensor 1204 ROJO; el resumen no expone campo de variables en atención/críticas; ${valor(s.ultimo_dato_recibido)}`, 'inicial');
    decision = `**${estado(r, id)} en resultado.json.** Las obligatorias API-181-01 y API-181-02 fueron aprobadas; PRE-181-01 cumple VERDE+ROJO según ORD-G92-026. API-181-03 está EXCLUIDA_DEL_ORACULO por decisión QA 2026-10-25, sin efecto en el veredicto.`;
    falta = `AMARILLO no fue construible en el sandbox (SBX-G92-02) y queda como observación de entorno.${runConciliado ? ' Newman aplicó la versión anterior que exigía AMARILLO; desajuste de automatización QA. API-181-03 se evaluó indebidamente como aserción en esa colección histórica.' : ''}`;
  } else if (id === 'TC-M03-182') {
    precondiciones = 'Productor autorizado con acceso a dos unidades; A (697) con 60 sensores y B (698) con tres, lecturas y alertas del escenario.';
    pasos = 'Se consultó el dashboard de A en dos páginas y el de B en una; se compararon los IDs de sensores y el único resumen de unidad de cada respuesta.';
    entradas = '`id_infraestructura=697&pagina=1&por_pagina=50`; `id_infraestructura=697&pagina=2&por_pagina=50`; `id_infraestructura=698&pagina=1&por_pagina=50`.';
    agregar('PRE-182-01', 'Precondición', 'Acceso a A y B, sensores disponibles', `A ${valor(o.total_a)} sensores; B ${valor(o.total_b)}`, 'a1');
    agregar('API-182-01', 'API', 'Sensores solo de la unidad filtrada', `A: ${valor(o.pagina1)}+${valor(o.pagina2)}; B: ${valor(o.total_b)}; IDs ajenos: ${o.ids_ajenos?.length ?? 'NO CONSTA'}`, 'a1');
    agregar('API-182-02', 'API', 'Resumen solo de la unidad filtrada', `A: id ${valor(o.resumen_a_p1?.id_infraestructura)} y ${valor(o.resumen_a_p2?.id_infraestructura)}; B: id ${valor(o.resumen_b?.id_infraestructura)}`, 'b1');
    decision = `**${estado(r, id)}.** Los tres listados y sus resúmenes quedaron limitados al filtro solicitado; no aparecieron IDs de la otra unidad.`;
    falta = 'El fallo de consolidación de 183 afecta el color del resumen A en página 1, pero no contradice el aislamiento del filtro comprobado aquí.';
  } else {
    precondiciones = 'Unidad A (697) con 60 sensores ordenados por ID; único ROJO en sensor 1196, posición 55, por alerta ESTRES_TERMICO CRITICO; los otros 59 permanecen VERDE.';
    pasos = 'Se consultó la página 1 (50 sensores) y la página 2 (10 sensores) del dashboard de A; se comparó el estado_general y la alerta activa en ambos resúmenes.';
    entradas = '`id_infraestructura=697&pagina=1&por_pagina=50` y `id_infraestructura=697&pagina=2&por_pagina=50`.';
    agregar('PRE-183-01', 'Precondición', '60 sensores; único ROJO en posición 55', `página 1: ${valor(o.pagina1)} VERDE; página 2: ${valor(o.pagina2)}, 1196 ROJO en posición ${valor(o.posicion_rojo)}`, 'a2');
    agregar('API-183-01', 'API', 'Página 1 con 50 sensores de A, sin ROJO', `total ${valor(o.total_a)}; página 1 ${valor(o.pagina1)} VERDE`, 'a1');
    agregar('API-183-02', 'API', 'estado_general ROJO en página 1 y 2', `página 1 ${valor(o.resumen_a_p1?.estado_general)}; página 2 ${valor(o.resumen_a_p2?.estado_general)}; alertas activas ${valor(o.resumen_a_p1?.alertas_activas_count)}`, 'a1');
    decision = `**${estado(r, id)}.** API-183-02 observó VERDE en la primera página pese al ROJO de 1196 en la segunda y a una alerta activa; el resumen cambia con la página.`;
    falta = 'La causa raíz no quedó comprobada; se requiere corrección y reevaluación autorizada de ambas páginas.';
  }
  const frases = filas.map((x) => `**${x.comprobacion}:** HTTP ${http(r, x.fase)}; ${x.obtenido}.`).join(' ');
  const tabla = filas.map((x) => `| ${x.comprobacion} | ${x.tipo} | ${x.esperado} | ${x.obtenido} | ${http(r, x.fase)} | ${x.estado} | ${enlace(x.evidencia)} |`).join('\n');
  return `### ${id}\n\n**Caso original y objetivo:** ${t.objetivo}\n\n**Precondiciones:** ${precondiciones}\n\n**Pasos ejecutados:** ${pasos}\n\n**Entradas:** ${entradas}\n\n**Esperado:** ${t.esperado}\n\n**Observado por API pública:** ${frases}\n\n**Decisión del caso:** ${decision}\n\n**Qué falta o cambió:** ${falta}\n\n| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |\n|---|---|---|---|---|---|---|\n${tabla}`;
}

function resumenBitacora(bitacora = []) {
  if (!bitacora.length) return 'Sin solicitudes registradas.';
  const grupos = new Map();
  for (const x of bitacora) {
    const ruta = String(x.ruta ?? 'SIN_RUTA').replace(/\/\d+(?=\/|\?|$)/g, '/{id}');
    const clave = [x.metodo, ruta, x.http ?? 'ERROR', x.en_run === true ? 'dentro' : 'fuera',
      x.eco_run === true ? 'sí' : x.eco_run === false ? 'no' : 'N/A'].join('\u0001');
    grupos.set(clave, (grupos.get(clave) ?? 0) + 1);
  }
  const filas = [...grupos].map(([clave, n]) => {
    const [metodo, ruta, http, fase, eco] = clave.split('\u0001');
    return `| ${n} | ${metodo} | \`${ruta}\` | ${http} | ${fase} | ${eco} |`;
  }).join('\n');
  return `Se registraron ${bitacora.length} solicitudes directas. Se agrupan por método, ruta, HTTP, fase y eco del RUN; el detalle saneado permanece en ${enlace('resultado.json')}.\n\n| Cantidad | Método | Ruta | HTTP | RUN | Eco |\n|---:|---|---|---:|---|---|\n${filas}`;
}

export function generarInformeG92(r) {
  const fallos = r.oficial ? (r.comprobaciones ?? []).filter((x) => x.tipo === 'ASSERT' &&
    x.estado === 'RECHAZADO' && r.casos?.[x.caso]?.estado_tecnico === 'OK') : [];
  const decision = !r.oficial ? 'NO CONCLUYENTE' : CASOS.some((id) => estado(r, id) === 'RECHAZADO') ? 'RECHAZADO' : 'APROBADO';
  const cuentas = Object.fromEntries(['APROBADO', 'RECHAZADO', 'BLOQUEADO', 'NO_CONCLUYENTE'].map((x) =>
    [x, CASOS.filter((id) => estado(r, id) === x).length]));
  const m = r.run_id?.match(/(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/);
  const fecha = m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6]} (marca del RUN; zona no acreditada)` : 'NO_VERIFICADO';
  const artefactoNewman = (() => { try { return JSON.parse(fs.readFileSync(path.join(r.directorio, REPORTE), 'utf8')); }
    catch { return null; } })();
  const estadisticas = artefactoNewman?.run?.stats;
  const idsFallidosNewman = (artefactoNewman?.run?.failures ?? []).map((x) =>
    x.error?.test?.match(/\[(?:PRE|ASSERT)\]\[([^\]]+)\]/)?.[1] ?? 'SIN_ID').filter(Boolean);
  const fallosNewman = idsFallidosNewman.length > 1
    ? `${idsFallidosNewman.slice(0, -1).join(', ')} y ${idsFallidosNewman.at(-1)}`
    : idsFallidosNewman[0] ?? 'ninguna';
  const runConciliado = r.run_id === 'RUN-G92-V1-20261031-022537';
  const notaResumen181 = runConciliado
    ? ' Dos fallos históricos de Newman corresponden a desajustes de automatización QA, sin efecto en ese veredicto.' : '';
  const notaRegistro = runConciliado
    ? ' aunque el registro histórico la conserve como ASSERT/APROBADO' : '';
  const problemasConciliados = runConciliado
    ? '\n\n- PRE-181-01: Newman aplicó la versión anterior de la colección que exigía AMARILLO; la precondición vigente por ORD-G92-026 es VERDE+ROJO. La colección no estaba sincronizada con el ejecutor.\n- API-181-03: Newman la evaluó como aserción fallida. El registro del intento 10 la incluyó entre las obligatorias por arrastre técnico del ejecutor, pese a la exclusión decidida por QA el 2026-10-25. El registro histórico se conserva sin cambios. Ambos son problemas de automatización QA, sin equipo de producto.' : '';
  const notaAnalisis181 = runConciliado
    ? ' Newman exigió AMARILLO con la colección anterior y evaluó API-181-03 como aserción, pese a su exclusión por QA; son desajustes técnicos, sin incidencia de producto.' : '';
  const evidencias = (r.evidencias ?? []).filter((x) => r.directorio && fs.existsSync(path.join(r.directorio, x)))
    .map((x) => `- ${enlace(x)}`).join('\n') || 'No hay archivos de evidencia acreditados.';
  const canarios = (r.canarios ?? []).map((x) => `- ${x.fase}, unidad ${x.area}: ${x.seguro ? 'CONFORME' : 'NO CONFORME'}, HTTP ${x.http ?? 'NO CONSTA'}; ${enlace(x.evidencia)}.`).join('\n') || 'No ejecutados.';
  const cierre = r.cierre?.rollback ?? {};
  const comprobacionesCierre = (cierre.comprobaciones ?? []).filter((x) => x.coincide === true).length;
  const tabla = CASOS.map((id) => `| ${id} | ${estado(r, id)} | ${r.casos?.[id]?.estado_tecnico ?? 'NO CONSTA'} |`).join('\n');
  const rls = (r.comprobaciones_tecnicas ?? []).map((x) => `- ${x.id}: ${x.estado}; ${x.motivo}; ${enlace(x.evidencia)}.`).join('\n') || 'No ejecutadas.';
  return `# TC-M03-G92 — ${decision}\n\n## 1. Identificación\n\nProyecto SIGAB/SGPMP; módulo 3, RF-58/CU04, CA-14; grupo G92; casos ${CASOS.join(', ')}; versión V${r.version}; ambiente TEST según el registro del RUN; fecha y hora ${fecha}; RUN ${r.run_id}; autorización ${r.autorizacion ?? 'NO_VERIFICADA'}. Rama NO_VERIFICADA; commit ${r.commit ?? 'NO_VERIFICADO'}. Colección Postman/Newman: ${r.newman?.length ?? 0} ejecución registrada, ${estadisticas?.requests?.total ?? 'NO CONSTA'} solicitudes y ${estadisticas?.assertions?.total ?? 'NO CONSTA'} aserciones (${estadisticas?.assertions?.failed ?? 'NO CONSTA'} fallidas). Node de regeneración ${process.version} (verificado localmente); versiones de Node, Newman y Postman del RUN: NO_VERIFICADAS en los artefactos; Cypress no exigido ni ejecutado.\n\n## 2. Resumen ejecutivo y decisión del grupo\n\n**Decisión del caso del grupo:** ${decision}. RUN ${r.oficial ? 'oficial' : 'no oficial'}, estado ${r.estado}. Total ${CASOS.length}: aprobados ${cuentas.APROBADO}, rechazados ${cuentas.RECHAZADO}, bloqueados ${cuentas.BLOQUEADO} y no concluyentes ${cuentas.NO_CONCLUYENTE}; ${fallos.length} incidencia funcional confirmada. El filtrado de unidades y el resumen ROJO de B se registraron como aprobados; el resumen de A en página 1 oculta el ROJO de la página 2. TC-M03-181 está APROBADO por PRE-181-01 y las obligatorias API-181-01/02.${notaResumen181}\n\n| Caso | Funcional | Técnico |\n|---|---|---|\n${tabla}\n\n## 3. Detalle por caso y comprobaciones API/UI\n\n${CASOS.map((id) => detalleCaso(r, id)).join('\n\n')}\n\nLa matriz exige API Postman/Newman para estos tres casos; no exige UI. Las tablas muestran el veredicto de resultado.json. API-181-03 se presenta como EXCLUIDA_DEL_ORACULO conforme a la decisión QA de 2026-10-25${notaRegistro}. PRE-181-01 se interpreta según ORD-G92-026.\n\n## 4. Incidencias y observaciones\n\n### Incidencia funcional confirmada\n\n${incidenciasProducto(r, fallos)}\n\n### Incidencias del entorno de pruebas\n\n${incidenciasSandbox(r)}\n\n### Observación documental separada\n\nLa matriz original menciona variables en atención/críticas. El sensor 1204 muestra la variable crítica Temperatura Ambiental; el resumen público no expone campo de variables en atención/críticas. El responsable QA confirmó el 2026-10-25 (SOL-G92-004 §9/§12 y SOL-G92-009) que RF-58 no exige ese campo en el resumen: API-181-03 es EXCLUIDA_DEL_ORACULO, observación documental sin efecto en veredicto u oficialidad.\n\n### Problemas técnicos QA\n\n${(r.problemas_tecnicos ?? []).map((x) => `- ${x}`).join('\n') || 'Ninguno adicional registrado en resultado.json.'}${problemasConciliados}\n\nEl intento histórico 1 registró timeout de GET global y riesgo de correo E7 sin envío confirmado; no constituye evidencia de producto de este RUN. ${runConciliado ? 'Los dos desajustes de 181 quedaron conciliados con las decisiones QA vigentes; el tercer fallo de Newman corresponde a API-183-02.' : ''}\n\n### RLS y comprobaciones técnicas\n\n${rls}\n\n## 5. Análisis de fallos\n\n**Hecho confirmado de 183:** GET público /iot/monitoreo/dashboard de A devuelve HTTP 200 en ambas páginas, con 60 sensores y una alerta activa. El primer punto de discrepancia es estado_general=VERDE en página 1, aunque el único ROJO (1196) está en posición 55 y página 2 devuelve ROJO. La causa raíz en TEST no está determinada. **Hipótesis:** el resumen se calcula sobre sensores paginados; la referencia local obtener_dashboard_use_case.py:100-108 procede de análisis anterior, sin versión ni commit verificados en esta orden. Desarrollo debe trazar la selección de sensores previa al agregado, corregir el cálculo global y comprobar ambas páginas en una reevaluación autorizada.\n\n**Análisis de 181:** VERDE y ROJO en B satisfacen PRE-181-01 según ORD-G92-026; API-181-01/02 acreditan resumen ROJO, alerta asociada y timestamp. AMARILLO no se construyó con la transacción sandbox; la explicación causal del worker postcommit RF-17 es PROBABLE según los antecedentes de código local.${notaAnalisis181} Código del producto consultado en esta orden: ninguna ruta; se leyeron la matriz original y RF-58 CA-14, además de la automatización y evidencias locales.\n\n## 6. Conclusiones y acciones\n\nSe comprobó el aislamiento por unidad de 182 y el ROJO de B con alerta y fecha en 181. No se cumplió CA-14 para A en la primera página (183). AMARILLO queda como observación de entorno y API-181-03 como observación documental excluida del oráculo, sin alterar el APROBADO de 181. Desarrollo debe atender INC-M03-183-G92. Una nueva evaluación de 183 requiere decisión y autorización propias; ${runConciliado ? 'esta edición documental no ejecutó pruebas.' : 'el informe refleja únicamente las pruebas del RUN.'}\n\n## 7. Herramientas, evidencias, bitácora y rollback\n\n**Newman:** una ejecución, ${estadisticas?.requests?.total ?? 'NO CONSTA'} solicitudes y ${estadisticas?.assertions?.total ?? 'NO CONSTA'} aserciones, ${estadisticas?.assertions?.failed ?? 'NO CONSTA'} fallidas: ${fallosNewman} según ${enlace(REPORTE)}. Reporte HTML: ${enlace('newman/newman-TC-M03-G92.html')}. No hubo sesiones Cypress.\n\n**Evidencias existentes del RUN:**\n\n${evidencias}\n\n**Bitácora resumida:**\n\n${resumenBitacora(r.bitacora)}\n\n**Canarios E7:**\n\n${canarios}\n\n**Cierre:** DELETE HTTP ${r.cierre?.run?.cierre_http ?? 'NO CONSTA'}; rollback ${cierre.estado ?? 'NO_VERIFICADO'} con ${comprobacionesCierre}/${cierre.comprobaciones?.length ?? 0} comprobaciones coincidentes y semilla ${cierre.semilla_intacta ? 'intacta' : 'NO_VERIFICADA'}. ${r.cierre?.motivo ?? ''} La reversión de correo E7 y auditoría de GET no fue verificada ni está incluida en el DELETE. Estado final del RUN: ${r.estado}.\n`;
}
