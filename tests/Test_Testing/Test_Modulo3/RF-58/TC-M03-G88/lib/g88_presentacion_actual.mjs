import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS_CASOS } from './g88_catalogo.mjs';

const GRUPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const enlace = (ruta, texto = ruta) => `[${texto}](./${encodeURI(ruta)})`;
const celda = (s) => String(s ?? 'no consta').replace(/[\r\n|]+/g, ' ').trim();
function claro(s) {
  let t = celda(s).replace(/; aserción=.*$/i, '');
  t = t.replace(/\{[^{}]*\}/g, (fragmento) => {
    try { return Object.entries(JSON.parse(fragmento)).map(([k, v]) => `${k}=${v}`).join('; '); }
    catch { return fragmento; }
  });
  return t;
}
const checks = (r, id) => (r.comprobaciones ?? []).filter(x => x.caso === id && x.tipo === 'ASSERT');
const fallos = (r, id) => checks(r, id).filter(x => x.estado === 'RECHAZADO');
function historial(r) {
  const carpeta = path.join(GRUPO, 'Resultados');
  const runs = [];
  if (fs.existsSync(carpeta)) for (const entrada of fs.readdirSync(carpeta, { withFileTypes: true })) {
    if (!entrada.isDirectory() || !/^RUN-G88-V\d+-\d{8}-\d{6}$/.test(entrada.name)) continue;
    try {
      const previo = JSON.parse(fs.readFileSync(path.join(carpeta, entrada.name, 'resultado.json'), 'utf8'));
      runs.push(previo.run_id === r.run_id ? r : previo);
    } catch { /* Los intentos sin resultado no se presentan como evaluaciones. */ }
  }
  if (!runs.some(x => x.run_id === r.run_id)) runs.push(r);
  return runs.sort((a,b) => (a.intento ?? 0) - (b.intento ?? 0))
    .map(x => `| ${x.intento ?? 'no consta'} | ${x.run_id} | ${x.estado ?? 'no consta'} | ${x.oficial === true ? 'OFICIAL' : x.oficial === false ? 'TECNICO' : 'INCIERTO: sin campo oficial'} |`);
}
function datos(r, id) {
  const c = checks(r, id);
  if (id === 'TC-M03-169') return {
    hizo: 'Administrador: sensor 552, especie 126 y umbral M09 15–30; ingresó 15, 22.5 y 30 y consultó el dashboard tras cada lectura.',
    observo: `POST de lecturas HTTP 201; GET HTTP 200; ${c.slice(1).map(x => claro(x.observado)).join('; ')}.`,
    porque: 'Los tres valores observados fueron VERDE en los bordes y dentro del rango ejecutado.' };
  if (id === 'TC-M03-170' || id === 'TC-M03-171') {
    const valores = fallos(r, id).map(x => /entrada=([^;]+)/.exec(x.observado ?? '')?.[1]).filter(Boolean);
    return { hizo: `Administrador: sensor 552, especie 126, umbral M09 15–30 y tolerancia derivada 1.5; ingresó ${valores.join(', ')} y consultó el dashboard después de cada lectura.`,
      observo: `POST HTTP 201 y GET HTTP 200; ${fallos(r, id).map(x => claro(x.observado)).join('; ')}.`,
      porque: `Las ${fallos(r, id).length} lecturas quedaron FUERA_DE_RANGO y el dashboard conservó 30 VERDE con indicador de anomalía; no mostró el color exigido.` };
  }
  if (id === 'TC-M03-172') return { hizo: 'Administrador: consultó cuatro umbrales M09 por API y abrió en Cypress el formulario de umbral para buscar la tolerancia T configurada en 2.',
    observo: `GET HTTP 200 sin campo T en umbral o niveles; Cypress ejecutó ${r.cypress?.casos?.[id]?.total_pruebas ?? 0} prueba y registró formulario sin control T; captura real.`,
    porque: 'API y formulario no permiten acreditar ni configurar T=2; faltó el dato exigido en ambos canales.' };
  if (id === 'TC-M03-180') return { hizo: 'Administrador: ingirió NH3=5 ppm del sensor 737 sin umbral; Productor: abrió el dashboard y verificó tarjeta, valor, unidad, etiqueta y color en cuatro pruebas Cypress.',
    observo: `POST HTTP 201; GET HTTP 200 con 5 ppm y GRIS; etiqueta “Sin umbral configurado” visible; ${r.cypress?.casos?.[id]?.total_pruebas ?? 0} pruebas UI, ${r.cypress?.casos?.[id]?.fallidas ?? 0} fallidas. Auditoría E7: aviso nuevo=0, previo registrado; entrega de correo no verificable por API.`,
    porque: 'Valor, unidad, GRIS, etiqueta y permanencia de la variable quedaron acreditados; el correo se deja como observación de alcance.' };
  return { hizo: 'Administrador: especie 220, área 504 y sensor 738; creó umbral M09 10–20, ingirió una sola lectura 15, consultó dashboard e historial, cambió M09 a 20–30 y repitió ambas consultas sin otra ingesta. Las barreras Edge quedaron pendientes.',
    observo: `Alta HTTP 201, edición HTTP 200 y GET HTTP 200; lectura 118471 con 15 VERDE antes y después; ${claro(c.at(-1)?.observado)}.`,
    porque: 'La misma lectura no se recalculó tras la edición: permaneció VERDE bajo 20–30.' };
}

const incidencias = [
  { id: 'DEV-G88-01', casos: ['TC-M03-170', 'TC-M03-171'], titulo: 'Lecturas de advertencia y críticas permanecen en 30 VERDE',
    requisito: 'RF-58 Fase 3, CA-2 y CA-16; matriz G88 pasos 2 y 3: AMARILLO dentro de T y ROJO fuera de T.',
    pre: 'Sensor 552, especie 126, umbral M09 15–30 y T derivada 1.5; lecturas aceptadas por HTTP 201.',
    pasos: ['Autenticar Administrador y comprobar sensor 552 y umbral M09 15–30.', 'Ingresar 13.65, 14.85, 30.15, 31.35, 13.35 y 31.65; consultar dashboard después de cada lectura.', 'Comparar valor, calidad, anomalía y color del dashboard con la zona de tolerancia.'],
    esperado: 'Los primeros cuatro valores deben mostrar AMARILLO; 13.35 y 31.65 deben mostrar ROJO con la tolerancia derivada.',
    obtenido: 'Los seis GET HTTP 200 conservaron valor 30.0000 VERDE; las lecturas se clasificaron FUERA_DE_RANGO con indicador_anomalia=true.',
    severidad: 'ALTA: seis condiciones de advertencia o crítica no llegan al semáforo operativo; el usuario ve 30 VERDE y carece de ese aviso.',
    impacto: 'El dashboard puede ocultar una condición que la matriz exige presentar en AMARILLO o ROJO.',
    hipotesis: 'Hipótesis: la clasificación de calidad excluye estas lecturas del valor operativo; la interacción con CA-6 requiere análisis de Desarrollo. No se confirma causa raíz.',
    cierre: 'Aclarar la relación entre CA-6 y la matriz G88, corregir la discrepancia y repetir las seis lecturas con dashboard e historial.' },
  { id: 'DEV-G88-02', casos: ['TC-M03-172'], titulo: 'T configurable ausente en API y formulario M09',
    requisito: 'RF-58 Fase 3 y matriz G88 paso 4: T=2 configurada prevalece sobre T por defecto; 18.5 y 31.5 AMARILLO.',
    pre: 'Administrador con acceso de lectura a cuatro umbrales M09 y formulario de umbral abierto en Cypress.',
    pasos: ['Autenticar Administrador y consultar GET de umbrales M09.', 'Revisar campos del umbral y sus niveles para T.', 'Abrir el formulario M09 en Cypress y buscar control de T antes de guardar.'],
    esperado: 'API y UI exponen y permiten configurar T=2 para evaluar 18.5 y 31.5 como AMARILLO.',
    obtenido: 'GET HTTP 200 sin T en cuatro umbrales ni niveles; una prueba Cypress encontró formulario sin control T y guardó captura.',
    severidad: 'MEDIA: la configuración específica T=2 está impedida; otros umbrales y el valor por defecto siguen disponibles.',
    impacto: 'No se puede aplicar la tolerancia propia exigida para el caso 172.',
    hipotesis: 'Hipótesis de implementación: revisar DTO/API M09 y control de formulario. La causa técnica no se establece con las dos observaciones públicas.',
    cierre: 'Exponer y persistir T en API/UI y ejecutar 18.5 y 31.5 con T=2 en un RUN autorizado.' },
  { id: 'DEV-G88-03', casos: ['TC-M03-266'], titulo: 'El semáforo no se recalcula después de editar M09',
    requisito: 'RF-58 Restricción 4 y matriz G88 paso 6: misma lectura 15 VERDE con 10–20 y ROJO/AMARILLO tras 20–30.',
    pre: 'Especie 220, sensor 738, lectura 118471; umbral inicial 10–20 y barreras M09→Edge sin publicación aplicada.',
    pasos: ['Autenticar Administrador, comprobar área 504 y ausencia inicial de umbral.', 'Crear M09 10–20, ingresar una lectura 15 y leer dashboard e historial.', 'Editar M09 a 20–30 y repetir los GET sin nueva ingesta.'],
    esperado: 'La misma lectura 15 deja de verse VERDE después de editar el umbral.',
    obtenido: 'POST M09 HTTP 201, PATCH HTTP 200; ambos GET HTTP 200 mostraron lectura 118471 con 15 VERDE.',
    severidad: 'ALTA: el recálculo dinámico exigido queda bloqueado sin alternativa en el dashboard; el estado visible permanece obsoleto.',
    impacto: 'Los cambios M09 no actualizan el color de la lectura ya presentada.',
    hipotesis: 'Hipótesis: el dashboard conserva un estado calculado con el umbral inicial; se requiere trazar el cálculo y persistencia antes de afirmar causa.',
    cierre: 'Repetir sin ingesta adicional y acreditar el nuevo color en dashboard e historial tras la corrección.' },
];

export function generarPresentacionActual(r) {
  const ids = IDS_CASOS;
  const decision = r.oficial ? (ids.some(id => r.casos?.[id]?.estado === 'RECHAZADO') ? 'RECHAZADO' : 'APROBADO') : 'NO OFICIAL';
  const aprobados = ids.filter(id => r.casos?.[id]?.estado === 'APROBADO').length;
  const rechazados = ids.filter(id => r.casos?.[id]?.estado === 'RECHAZADO').length;
  const l = [`# TC-M03-G88 — ${decision}`, '', '## Decisión del caso', '',
    `**Caso agrupado:** TC-M03-G88, RF-58. **Casos originales:** ${ids.join(', ')}.`,
    `**Decisión:** ${decision}. **Motivo:** ${aprobados} aprobados, ${rechazados} rechazados; 170/171 conservan 30 VERDE ante seis lecturas externas, 172 carece de T en API/UI y 266 conserva 15 VERDE tras editar M09.`,
    `**RUN oficial:** ${r.oficial === true ? 'sí' : 'no'}. **Qué falta:** ${r.oficial === true ? 'Resolver las tres incidencias funcionales y repetirlas en evaluación autorizada.' : celda(r.motivo_no_oficial ?? 'El registro QA aún no acredita el contrato de oficialidad.')}`, '',
    '| Caso | Comprobación | Decisión | Motivo breve |', '| --- | --- | --- | --- |'];
  for (const id of ids) {
    const c = r.casos?.[id] ?? {};
    l.push(`| ${id} | ${checks(r, id).map(x => x.id).join(', ') || 'ninguna'} | ${c.estado ?? 'sin veredicto'} | ${celda(datos(r, id).porque)} |`);
  }
  l.push('', '## Detalle por caso', '');
  for (const id of ids) {
    const d = datos(r, id), estado = r.casos?.[id]?.estado ?? 'SIN VEREDICTO';
    l.push(`### ${id}`, '', `**Qué se hizo:** ${d.hizo}`, `**Qué se esperaba:** ${CASOS[id].esperado} (matriz G88, RF-58).`,
      `**Qué se observó:** ${d.observo}`, `**Por qué ${estado}:** ${d.porque}`, '');
  }
  l.push('## Identificación y alcance', '',
    `RUN ${r.run_id}; intento ${r.intento}; V${r.version}; ambiente ${r.ambiente}; autorización ${r.referencia}; inicio ${r.inicio}; fin ${r.fin}; commit ${r.commit}.`,
    `Herramientas verificadas: ${Object.entries(r.herramientas ?? {}).map(([k,v]) => `${k}: ${v}`).join('; ')}. Newman: ${r.newman_casos?.length ?? 0} casos en una colección; Cypress: ${r.cypress?.total_pruebas ?? 0} pruebas.`,
    'Fuente de oráculos: fila TC-M03-G88 de Casos_Prueba(Modulo3 Agrupado).csv y RF-58, Fase 3, CA-2/12/16, E7 y Restricción 4. Los ejemplos de matriz 35–39 y 20–30 se ejecutaron con la semilla 15–30 y valores proporcionales; los colores esperados se conservaron. Esta sustitución de datos no prueba literalmente los valores originales.', '',
    '## Esperado y observado: comprobaciones API/UI', '', '| Caso | Fuente | Comprobación | Decisión | Esperado | Observado |', '| --- | --- | --- | --- | --- | --- |');
  for (const id of ids) for (const x of checks(r, id))
    l.push(`| ${id} | ${x.fuente} | ${x.id} | ${x.estado} | ${celda(CASOS[id].esperado)} | ${claro(x.observado)} |`);
  l.push('', '## Observaciones y alcance', '',
    'E7, hecho: la auditoría registró cero avisos nuevos y un aviso previo para el sensor 737. Inferencia: el patrón es compatible con deduplicación de 24 h. La entrega SMTP no es comprobable por API y queda como observación; el resto de 180 se evaluó por API y UI.',
    `Cypress: 172 ejecutó ${r.cypress?.casos?.['TC-M03-172']?.total_pruebas ?? 0} prueba; 180 ejecutó ${r.cypress?.casos?.['TC-M03-180']?.total_pruebas ?? 0}. Ningún APROBADO de UI se basa en cero ejecuciones.`,
    `RF-61-A: ${(r.hallazgos_producto ?? []).length} hallazgos de vínculo registrados por separado en resultado.json; no cambian RF-58.`, '',
    '## Incidencias de producto', '');
  const presentes = incidencias.filter(i => i.casos.some(id => r.casos?.[id]?.estado === 'RECHAZADO'));
  if (!presentes.length) l.push('No hay discrepancias funcionales con veredicto RECHAZADO en este RUN.', '');
  for (const i of presentes) {
    const evidencias = ['resultado.json', 'newman/newman-TC-M03-G88.json', ...((r.evidencias ?? []).filter(x => i.casos.includes('TC-M03-172') && /TC-M03-172.*\.png$/.test(x)))];
    l.push(`### ${i.id} — ${i.titulo}`, '', `**Casos:** ${i.casos.join(', ')}. **Equipo inicial:** Desarrollo. **Certeza:** CONFIRMADA para la discrepancia pública; causa raíz no confirmada.`,
      `**Severidad e impacto:** ${i.severidad}`, `**Requisito:** ${i.requisito}`, `**Precondiciones:** ${i.pre}`,
      '**Pasos reales:**', ...i.pasos.map((p,n) => `${n+1}. ${p}`), '',
      `**Esperado:** ${i.esperado}`, `**Obtenido:** ${i.obtenido}`,
      ...i.casos.flatMap(id => fallos(r, id).map(x => `- ${x.id} ${x.estado}: ${claro(x.observado)}`)),
      `**Evidencia:** ${[...new Set(evidencias.filter(x => (r.evidencias ?? []).includes(x)))].map(enlace).join(', ')}; comprobaciones ${i.casos.flatMap(id => fallos(r,id).map(x => x.id)).join(', ')}.`,
      `**Fundamento del primer contacto:** discrepancia en API pública${i.casos.includes('TC-M03-172') ? ' y UI' : ''}; Desarrollo atiende la funcionalidad observada, sin atribuirle causa técnica.`,
      `**Hecho probado:** ${i.obtenido} **Inferencia de impacto:** ${i.impacto} **${i.hipotesis.startsWith('Hipótesis') ? 'Hipótesis' : 'Análisis'}:** ${i.hipotesis.replace(/^Hipótesis: /, '')}`,
      `**Para cerrar:** ${i.cierre}`, '');
  }
  l.push('## Comprobaciones técnicas DBA-01', '', '| Comprobación | Estado | Observado |', '| --- | --- | --- |');
  for (const x of r.comprobaciones_tecnicas ?? []) l.push(`| ${x.id} | ${x.estado} | ${claro(x.observado)} |`);
  l.push('', `Cuentas: ${(r.cuentas ?? []).map(x => `${x.etapa}: HTTP ${x.http}, rol=${x.rol_correcto}, identidad=${x.identidad_correcta}`).join('; ') || 'sin registro'}.`,
    `Acceso Administrador: ${(r.acceso_administrador ?? []).map(x => `${x.ruta}: HTTP ${x.http}`).join('; ') || 'sin registro'}.`, '',
    '## Barrera M09→Edge y Newman/Cypress', '',
    `Barrera: ${(r.bitacora ?? []).filter(x => /BARRERA|ALTA_M09|EDICION_M09/.test(x.etapa ?? '')).map(x => `${x.etapa}: ${x.estado ?? x.estado_sincronizacion ?? 'registrado'}`).join('; ') || 'consultar comprobaciones PRE en resultado.json'}. No se infiere reversión MQTT por DELETE.`,
    `Newman: ${enlace('newman/newman-TC-M03-G88.json')} y ${enlace('newman/newman-TC-M03-G88.html')}. Cypress: ${(r.evidencias ?? []).filter(x => x.startsWith('cypress/') && /\.png$/.test(x)).map(enlace).join(', ') || 'sin capturas registradas'}.`, '',
    '## Historial de intentos', '',
    '| Intento | RUN | Estado registrado | Clasificación según campo oficial |', '| --- | --- | --- | --- |',
    ...historial(r), '', `Motivos de los intentos anteriores: ${enlace('../../README.md', 'README del grupo')} y sus informes conservados.`, '',
    '## Cierre y rollback', '',
    `DELETE HTTP ${r.cierre?.run?.cierre_http ?? r.cierre?.cierre_http ?? 'no consta'}; rollback ${r.cierre?.rollback?.verificado === true ? 'verificado' : 'no verificado'}; conclusión ${r.cierre?.rollback?.conclusion ?? 'no consta'}. Umbral 266: ${r.cierre?.rollback?.umbral_run_266?.estado ?? 'no consta'}; umbral QA 91: ${r.cierre?.rollback?.umbral_qa_91?.estado ?? 'no consta'}. Cierre y rollback son comprobaciones distintas del veredicto RF-58.`, '',
    '## Evidencias y acciones', '',
    `${(r.evidencias ?? []).map(enlace).join(', ') || 'Sin evidencias registradas.'}`, '',
    `Estado final: ${decision}. ${r.oficial ? 'Conservar este RUN para registro QA y atender DEV-G88-01/02/03.' : `Pendiente de oficialidad: ${r.motivo_no_oficial ?? 'motivo no registrado'}`}`);
  return l.join('\n') + '\n';
}
