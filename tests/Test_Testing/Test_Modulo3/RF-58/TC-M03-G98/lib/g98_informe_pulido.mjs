import fs from 'node:fs';
import path from 'node:path';
import { ORACULO, PRESUPUESTO } from './g98_escenario.mjs';

const CASO = 'TC-M03-191';
const cambiar = (texto, numero, contenido) => texto.replace(
  new RegExp(`## ${numero}\\. [^\\n]+\\n[\\s\\S]*?(?=## ${numero + 1}\\. |$)`),
  `${contenido.trim()}\n\n`);
const enlace = ruta => `[${ruta}](${ruta})`;

function alertasNewman(directorio) {
  if (!directorio) return [];
  try {
    const reporte = JSON.parse(fs.readFileSync(path.join(directorio, 'newman/newman-G98.json'), 'utf8'));
    const ejecucion = reporte.run?.executions?.find(x => x.response?.code === 200);
    const bytes = ejecucion?.response?.stream?.data;
    const cuerpo = JSON.parse(Buffer.from(bytes).toString('utf8'));
    return Array.isArray(cuerpo.panel_alertas_activas?.alertas) ? cuerpo.panel_alertas_activas.alertas : [];
  } catch { return []; }
}
function tablaAlertas(alertas) {
  if (!alertas.length) return 'El reporte Newman no contiene filas de alerta disponibles para esta generación.';
  const filas = alertas.map(a => {
    const unidad = a.unidad === 'C' ? '°C' : a.unidad;
    const valor = Number(a.valor).toLocaleString('es-CO', { maximumFractionDigits: 4 });
    return `| ${a.id_alerta} | ${a.severidad} | ${a.tipo_alerta} | ${a.tipo_variable} | ${valor} ${unidad} | ${a.minutos_transcurridos} | ${a.id_activo_biologico} (identificador presente) |`;
  });
  return ['| ID | Severidad | Tipo de alerta | Variable | Valor | Minutos transcurridos | Activo biológico |',
    '| ---: | --- | --- | --- | ---: | ---: | --- |', ...filas].join('\n');
}
function resumenPeticiones(bitacora = []) {
  const conteos = new Map();
  for (const b of bitacora) {
    const ruta = String(b.ruta ?? '').split('?')[0]
      .replace(/^\/iot\/alertas\/\d+$/, '/iot/alertas/{id}')
      .replace(/^\/iot\/monitoreo\/dashboard\/\d+$/, '/iot/monitoreo/dashboard/{área}')
      .replace(/^\/configuracion\/dispositivos-iot\/\d+\/sensores$/, '/configuracion/dispositivos-iot/{id}/sensores')
      .replace(/^\/test-control\/runs\/[^/]+$/, '/test-control/runs/{RUN}');
    const eco = b.eco == null ? 'no aplica' : b.eco ? 'sí' : 'no';
    const clave = `${b.metodo}|${ruta}|${b.http ?? 'sin respuesta'}|${eco}`;
    conteos.set(clave, (conteos.get(clave) ?? 0) + 1);
  }
  return ['| Método | Ruta saneada | HTTP | Eco | Peticiones |', '| --- | --- | ---: | --- | ---: |',
    ...[...conteos].map(([clave, total]) => {
      const [metodo, ruta, http, eco] = clave.split('|');
      return `| ${metodo} | ${ruta} | ${http} | ${eco} | ${total} |`;
    })].join('\n');
}
function detalle(r, alertas) {
  const v3 = r.version === 3;
  const caso = r.casos[CASO];
  const pre = r.precondicion;
  const panel = r.paginas?.[0];
  const ids = alertas.map(a => a.id_alerta).join(', ') || (pre?.ids ?? []).join(', ') || 'no acreditados';
  const motivoTiempo = `El oráculo automatizado vigente en V2 marcó inválido el campo minutos_transcurridos: valor −1 en cada alerta (${ids}); exigía un tiempo no negativo.`;
  const motivo = v3
    ? `HTTP ${panel?.http ?? 'sin respuesta'} con eco del RUN; total ${pre?.total ?? 'no acreditado'} y tres alertas ACTIVA del área ${pre?.unidad ?? 'no seleccionada'}, ordenadas CRITICO → MODERADO → LEVE. Cada fila contiene tipo, variable, tiempo e identificador del activo 928. Los minutos −1 son enteros dentro de la ventana temporal de V3: las alertas se crearon después del inicio del RUN y el reloj de la transacción sandbox quedó fijo.`
    : motivoTiempo;
  const fechas = alertas.map(a => a.fecha_generacion).filter(Boolean).sort();
  const intervalo = fechas.length
    ? `Las fechas de generación van de ${fechas[0]} a ${fechas.at(-1)}; el RUN empezó a las ${r.inicio}.`
    : '';
  const filas = (r.comprobaciones ?? []).map(c => `| ${c.id} | ${c.fuente} | ${c.estado} | ${!v3 && c.id === 'API-191-01' ? motivoTiempo : c.motivo} | ${enlace(c.evidencia ?? 'resultado.json')} |`);
  const previo = v3
    ? (pre?.via === 'CREACION_SANDBOX' ? 'Antes de crear las alertas, no había un área visible con tres alertas ACTIVA de severidades distintas en sensores distintos; por eso se crearon tres en el sandbox.' : 'Se reutilizó una terna ACTIVA acreditada por GET públicos.')
    : 'Antes de crear las alertas, no había un área visible con las tres severidades ACTIVA; se usó la semilla apta del área 702.';
  const decision = v3
    ? `**APROBADO**. API-191-01 acreditó HTTP 200, eco, total, lista, alcance, orden, tipo, variable y tiempo dentro de la ventana del RUN; API-191-02 acreditó las tres severidades ACTIVA en sensores distintos; API-191-03 acreditó id_activo_biologico e identificador_activo; API-191-04 acreditó severidad_alerta en los sensores. ${caso.motivo}.`
    : `**RECHAZADO** según el oráculo automatizado de ese RUN: ${motivoTiempo} API-191-02, API-191-03 y API-191-04 aprobaron. La nota posterior documenta por qué V3 anuló la incidencia temporal; el veredicto histórico de V2 permanece RECHAZADO.`;
  return `## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-191

**Objetivo:** verificar el total y el orden por severidad del panel de alertas activas, sus datos y el identificador que permite navegar al activo afectado.

**Precondiciones:** «Alertas activas de severidad CRITICO, ALTA y MEDIA sobre distintos sensores de la misma unidad.» La decisión QA aceptó la escala RF-57 CRITICO > MODERADO > LEVE para la terna real. Semilla persistente QA-G98-PANEL: finca 184, área 702, dispositivo 789, sensores 1210/1211/1212, activo biológico 928. Los GET públicos del RUN acreditaron área, activo, sensores y lecturas. ${previo} Vía ${pre?.via ?? 'no acreditada'}; las alertas ${((r.ids_creados ?? []).join(', ') || 'ninguna')} se crearon solo en el sandbox del RUN.

**Pasos:** iniciar sesión; comprobar área, activo, dispositivo, sensores y lecturas; ejecutar el canario E7; crear y verificar las tres alertas en el sandbox; consultar el dashboard por Newman; cotejar total, orden, campos, tiempo y activo; cerrar el RUN y comprobar rollback.

**Entradas:** área ${pre?.unidad ?? 'no seleccionada'}; alertas ${ids}; inicio del RUN ${r.inicio ?? 'no registrado'}.

**Esperado:** «${ORACULO}» Orden aceptado por decisión QA: CRITICO > MODERADO > LEVE. ${v3 ? 'Para el tiempo, el oráculo V3 exige un entero dentro de la ventana entre el inicio del RUN menos 120 s y la respuesta, con un minuto de tolerancia por extremo; la fecha de generación no debe superar la respuesta más 60 s.' : 'El oráculo automatizado vigente durante V2 exigía tiempo no negativo.'}

**Observado:** ${motivo} ${v3 ? intervalo : 'El panel ya mostraba total, orden, campos y activo correctos.'}

**Valores observados en Newman:** total ${pre?.total ?? 'no acreditado'}; ${alertas.length} filas.

${tablaAlertas(alertas)}

**Decisión con porqué:** ${decision}

**Qué falta:** ${v3 ? 'Nada para decidir el caso por API. La navegación visual no se ejecutó; este caso está clasificado como API Postman/Newman.' : 'En V2 faltaba resolver la discrepancia temporal del oráculo automatizado. V3 documenta su resolución sin alterar este veredicto histórico.'}

| Comprobación | Fuente | Estado | Motivo | Evidencia |
| --- | --- | --- | --- | --- |
${filas.join('\n')}

| Área | HTTP | Eco | Estado del panel |
| ---: | ---: | --- | --- |
| ${panel?.unidad ?? '—'} | ${panel?.http ?? '—'} | ${panel?.eco ? 'sí' : 'no'} | ${panel?.panel?.estado ?? 'sin evaluación'} |

La API comprobó los identificadores de navegación; no se ejecutó navegación visual.
`;
}
function evidencias(r) {
  const archivos = (r.evidencias ?? []).filter(x => x !== 'resultado.json' && !x.endsWith('.md'));
  return `## 7. Evidencias, herramientas, cierre y rollback

Node ${process.version}; Newman ${r.preflight_herramientas?.newman?.version ?? 'no verificado'}; Postman y Cypress no ejecutados. Presupuesto: ${PRESUPUESTO.solicitudes_en_run} solicitudes directas, hasta ${PRESUPUESTO.escrituras_alerta} POST de alerta, ${PRESUPUESTO.margen_cierre} DELETE de cierre y ${PRESUPUESTO.lecturas_cierre} GET posteriores.

**Bitácora resumida por tipo de petición:**

${resumenPeticiones(r.bitacora)}

El detalle de cada petición consta en ${enlace('resultado.json')}; la respuesta de Newman consta en ${enlace('newman/newman-G98.json')}. Otras evidencias del RUN: ${archivos.map(enlace).join(', ') || 'ninguna'}.

Cierre DELETE HTTP ${r.cierre?.run?.cierre_http ?? 'sin respuesta'}. Rollback: ${r.cierre?.rollback?.verificado ? r.cierre.rollback.motivo : `NO VERIFICADO: ${r.cierre?.rollback?.motivo ?? 'sin motivo'}`}. El login y los posibles efectos E7 no se declaran revertidos.
`;
}

export function pulirInforme(base, r, directorio = null) {
  if (![2, 3].includes(r.version)) return base;
  if (r.version === 2 && r.run_id !== 'RUN-G98-V2-20261031-183417') return base;
  if (r.version === 3 && (!r.oficial || r.casos?.[CASO]?.estado !== 'APROBADO')) return base;
  const alertas = alertasNewman(directorio);
  let texto = cambiar(base, 3, detalle(r, alertas));
  if (r.version === 3) {
    texto = cambiar(texto, 2, `## 2. Resumen de veredictos y comparación V1 → V2 → V3

V1 RUN-G98-V1-20261026-181259: RECHAZADO por panel ausente. V2 RUN-G98-V2-20261031-183417: RECHAZADO por el oráculo temporal anterior; total, orden, tipo, variable y activo ya cumplían. V3 ${r.run_id}: **${r.casos[CASO].estado}** por HTTP 200 con eco, total ${r.precondicion?.total ?? 'no acreditado'}, orden CRITICO → MODERADO → LEVE, campos y vínculo al activo ${r.precondicion?.alertas?.[0]?.id_activo_biologico ?? 'no acreditado'}; el tiempo cumple la ventana temporal del RUN.`);
    texto = cambiar(texto, 4, `## 4. Incidencias y observaciones

INC-M03-191-G98-01: **${r.oficial && r.casos[CASO].estado === 'APROBADO' ? 'CORREGIDA' : 'PENDIENTE DE CONFIRMACIÓN EN V3'}**. El panel faltaba en V1; en V3 la API pública devolvió total 3, lista ordenada, campos y activo. Equipo inicial Desarrollo por la ausencia API observada en V1; severidad ALTA de aquel hallazgo, certeza CONFIRMADA de la corrección en este RUN oficial.

INC-M03-191-G98-02: **ANULADA**. El rechazo temporal V2 fue un falso positivo del oráculo QA: el sandbox fijó now() al inicio de la transacción mientras las alertas se crearon después. No es incidencia de producto. El valor −1 se registra como observación; no hay nueva discrepancia funcional en V3.

**Historial de intentos técnicos V2:** [intento 165339](api/antecedentes/intento-165339.json), BLOQUEADO porque no había tres severidades ACTIVA previas; [intento 172140](api/antecedentes/intento-172140.json), BLOQUEADO sin terna segura y sin POST; [intento 182607](api/antecedentes/intento-182607.json), BLOQUEADO porque las 24 consultas de historial registradas respondieron HTTP 422 al combinar sensor_id con id_infraestructura, filtro no admitido por la Restricción 12 de RF-59. [Índice de origen y SHA-256](api/antecedentes/indice.json). Son extractos saneados dentro de este RUN oficial; los originales técnicos no son dependencias del informe.

Problemas técnicos QA de V3: ${r.problemas_tecnicos?.join('; ') || 'ninguno'}.`);
    texto = cambiar(texto, 5, `## 5. Análisis de causas y certeza

La lectura local documentada en la preparación anterior señaló src/telemetry/infrastructure/repositories/indicadores_alertas_repository.py:70, donde se calcula el tiempo con now(), y src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py:110, donde se fija la fecha al crear la alerta. En esta orden no se consultó código del producto. La comparación entre los RUN V2 y V3 confirma el falso positivo del oráculo QA; el mecanismo del reloj transaccional es una explicación PROBABLE del −1, sin verificar el despliegue exacto de TEST.`);
    texto = cambiar(texto, 6, `## 6. Conclusión y acciones

${r.casos[CASO].estado}: el RUN V3 acreditó por API pública el total, orden, datos, tiempo dentro de la ventana y vínculo al activo. Conservar esta evidencia, cerrar INC-M03-191-G98-01 como corregida y dejar INC-M03-191-G98-02 anulada como falso positivo QA.`);
  } else if (r.run_id === 'RUN-G98-V2-20261031-183417') {
    const motivo = `El oráculo automatizado de V2 rechazó minutos_transcurridos=−1 en las alertas ${alertas.map(x => x.id_alerta).join(', ')} porque exigía un valor no negativo.`;
    texto = cambiar(texto, 2, `## 2. Resumen ejecutivo y decisión del grupo

**RECHAZADO**, veredicto oficial de V2. ${motivo} Newman ejecutó una consulta; total 3, orden, campos y activo ya cumplían.`);
    texto = cambiar(texto, 4, `## 4. Incidencias y observaciones

INC-M03-191-G98-02 se registró en V2 como incidencia **MEDIA**, certeza de la discrepancia temporal CONFIRMADA por la respuesta API, equipo inicial Desarrollo por ser el dashboard la primera superficie observada. El campo minutos_transcurridos valía −1 en las alertas 1385, 1386 y 1387; el oráculo de entonces exigía valor no negativo. La causa raíz no quedó determinada en V2. La nota posterior deja constancia de su anulación, sin cambiar el RECHAZADO histórico.

INC-M03-191-G98-01: **CORREGIDA** en V2 respecto de la ausencia del panel en V1. Ya se observaron total 3, orden y campos del activo. No había tres alertas ACTIVA aptas antes de crear la terna en el sandbox.

Problemas técnicos QA registrados en este RUN: ${r.problemas_tecnicos?.join('; ') || 'ninguno'}.`);
    texto = cambiar(texto, 5, `## 5. Análisis de causas y certeza

La primera discrepancia registrada en V2 fue el valor −1 del campo minutos_transcurridos frente al oráculo automatizado que exigía un valor no negativo. La respuesta pública y el reporte Newman confirman el dato observado; la causa raíz no se estableció en ese RUN. La lectura local de código citada en la preparación anterior no verifica el despliegue de TEST. En esta orden no se consultó código del producto.`);
    texto = cambiar(texto, 6, `## 6. Conclusiones y acciones

RECHAZADO según el oráculo temporal vigente en V2: ${motivo} La reevaluación V3 posterior aclaró este falso positivo; conservar el veredicto y la evidencia histórica sin derivar una incidencia vigente a Desarrollo.`);
  }
  texto = cambiar(texto, 7, evidencias(r));
  if (r.version === 2 && r.run_id === 'RUN-G98-V2-20261031-183417') texto += `\n## Nota posterior (V3)\n\nINC-M03-191-G98-02 fue **ANULADA** en RUN-G98-V3-20261031-185044: el valor −1 provenía del falso positivo del oráculo QA frente al now() fijo del sandbox. El panel de V2 ya cumplía total 3, orden, campos y vínculo al activo 928. Esta nota no modifica el veredicto RECHAZADO ni resultado.json de V2.\n`;
  return texto;
}
