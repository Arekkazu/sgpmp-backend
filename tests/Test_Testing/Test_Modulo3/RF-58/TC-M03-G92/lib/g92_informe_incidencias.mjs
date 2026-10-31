import fs from 'node:fs';
import path from 'node:path';

const ANTECEDENTES = 'api/antecedentes-sandbox';
const enlace = (nombre) => `[${nombre}](${ANTECEDENTES}/${nombre})`;

export function incidenciasProducto(r, fallos) {
  const lineas = [];
  if (fallos.some((x) => x.id === 'API-183-02')) {
    const o = r.casos['TC-M03-183']?.observado ?? {};
    lineas.push(`**INC-M03-183-G92 — TC-M03-183: resumen de unidad cambia con la página.**

- **Esperado:** con 60 sensores de A (697) y único ROJO en 1196, posición 55, estado_general ROJO en página 1 y 2.
- **Obtenido y primer punto comprobado:** GET público /iot/monitoreo/dashboard HTTP 200; página 1 ${o.resumen_a_p1?.estado_general ?? 'NO CONSTA'}, página 2 ${o.resumen_a_p2?.estado_general ?? 'NO CONSTA'}, alertas_activas_count ${o.resumen_a_p1?.alertas_activas_count ?? 'NO CONSTA'} en página 1. API-183-02 RECHAZADO.
- **Evidencia:** [Newman](newman/newman-TC-M03-G92.json), [resultado.json](resultado.json).
- **Impacto y severidad:** **ALTA**; el productor puede ver VERDE mientras existe un sensor ROJO fuera de la página, sin alternativa en ese resumen.
- **Equipo inicial:** **Desarrollo**; la primera discrepancia se observa en la respuesta de la API pública. Esta derivación no atribuye causa raíz.
- **Certeza:** discrepancia **CONFIRMADA** en TEST; causa raíz **NO DETERMINADA**. **Hipótesis:** agregación limitada a la página; el archivo local obtener_dashboard_use_case.py:100-108 es una pista no verificada contra el commit de TEST.
- **Ruta de investigación y acción correctiva:** revisar el agregado del resumen antes de paginar sensores, corregirlo y comprobar ambas páginas por API pública en reevaluación autorizada.
- **Reproducción:** 1) Usar unidad A 697 con 60 sensores, lectura de 25 °C en todos y alerta ESTRES_TERMICO CRITICO activa en 1196 (posición 55). 2) GET /iot/monitoreo/dashboard?id_infraestructura=697&pagina=1&por_pagina=50. 3) Repetir con pagina=2. 4) Comparar estado_general con el ROJO de 1196 y alertas_activas_count=1.`);
  }
  for (const x of fallos.filter((y) => y.id !== 'API-183-02'))
    lineas.push(`${x.id}: discrepancia de API pública confirmada; detalle y equipo inicial pendientes de evidencia específica. [Newman](${x.evidencia ?? 'newman/newman-TC-M03-G92.json'}).`);
  return lineas.join('\n\n') || 'Ninguna confirmada.';
}

export function incidenciasSandbox(r) {
  const archivos = ['indice.json', 'sbx-g92-01-error-tiempo.json',
    'sbx-g92-01-asociacion.json', 'sbx-g92-02-semaforo.json'];
  if (!r.directorio || !archivos.every((x) =>
    fs.existsSync(path.join(r.directorio, ANTECEDENTES, x))))
    return 'Sin antecedentes de sandbox incorporados en este RUN.';
  const texto = `Estos antecedentes describen limitaciones del sandbox QA; **no son defectos funcionales del producto**. El índice conserva el RUN y el SHA-256 de cada original: ${enlace('indice.json')}.

- **SBX-G92-01.** En la transacción única del RUN, \`NOW()\` queda fijo en su apertura (4007369f8d3d_fix_fn_ingesta_telemetria.py:49,593,651). La ingesta exige también fecha_asociacion ≤ timestamp_captura (15cb081c4835_fix_segundofningestatelemetria.py:181-190), mientras la asociación toma el reloj real (sensor_area.py:47). En el intento 012236, POST /iot/telemetria devolvió HTTP 400 ERROR_TIEMPO pese a que la captura no era futura respecto del reloj del servidor; en el intento 013032, una captura anterior a la apertura para un sensor asociado dentro del RUN devolvió HTTP 401 ERROR_AUTENTICACION, mensaje «Dispositivo o sensor no encontrado o inactivo» (traducción genérica en ingerir_telemetria_use_case.py:26). Impacto: impide ingestas de sensores asociados dentro del RUN. Mitigación aplicada: semilla persistente de las áreas 697/698. Equipo de atención del entorno: **DBA**, con apoyo de **Desarrollo**; la primera discrepancia está en la semántica temporal de la transacción sandbox. Severidad **MEDIA**, limitada a la preparación QA; certeza de los HTTP **CONFIRMADA**, explicación causal **PROBABLE** por código local. Evidencia: ${enlace('sbx-g92-01-error-tiempo.json')} (origen 012236) y ${enlace('sbx-g92-01-asociacion.json')} (origen 013032). **Esperado:** ingesta válida con sensor asociado y captura temporalmente válida. **Obtenido:** HTTP 400 ERROR_TIEMPO y HTTP 401 ERROR_AUTENTICACION en los antecedentes. **Hipótesis:** diferencia entre reloj transaccional y reloj real de asociación; causa no confirmada en TEST. **Ruta y acción:** DBA y Desarrollo deben contrastar marcas de transacción/asociación e indicar una forma segura de preparar sensores. **Reproducción:** 1) abrir RUN sandbox; 2) asociar sensor nuevo dentro de la transacción; 3) enviar telemetría con captura anterior a la apertura y luego con captura posterior a la asociación; 4) comparar HTTP y marcas. No repetir sin autorización.
- **SBX-G92-02.** La clasificación RF-17 por niveles pasa por el worker postcommit con conexión propia y lecturas confirmadas (postcommit_worker.py:155,173-185; reclasificar_semaforo_use_case.py:89). En el intento 021342, el sensor 1203 con 19,5 °C y el 1196 con 16 °C quedaron VERDE; el 1204 con 16 °C quedó ROJO por alerta CRITICO. Las lecturas del RUN no se confirman durante la evaluación. Impacto: AMARILLO de la precondición de TC-M03-181 no es construible por lectura en este sandbox; el ROJO se obtuvo por alerta. Mitigación: conservar esa limitación documentada y evaluar el escenario ROJO por alerta sin alterar el oráculo. Equipo de atención del entorno: **DBA**, con apoyo de **Desarrollo**; la primera limitación se observa en la visibilidad de lecturas entre transacciones. Severidad **MEDIA**, porque bloquea escenarios QA dependientes del color por lectura; certeza de los colores **CONFIRMADA**, explicación causal **PROBABLE** por código local. Evidencia: ${enlace('sbx-g92-02-semaforo.json')} (origen 021342). **Esperado:** lecturas de atención clasificadas AMARILLO según RF-17 durante la prueba. **Obtenido:** 1203 a 19,5 °C y 1196 a 16 °C siguieron VERDE; 1204 a 16 °C fue ROJO por alerta CRITICO. **Hipótesis:** worker postcommit no ve lecturas sin confirmar; causa no acreditada contra el despliegue TEST. **Ruta y acción:** DBA y Desarrollo deben comprobar visibilidad transaccional y definir un escenario que permita observar AMARILLO. **Reproducción:** 1) ingestar lectura de atención en sandbox; 2) consultar GET /iot/monitoreo/dashboard dentro del RUN; 3) comparar semáforo antes y después del commit en evaluación autorizada. No repetir sin autorización.`;
  return texto.replace(/ (Impacto:|Mitigaci\u00f3n:|Equipo de atenci\u00f3n del entorno:|Severidad |Evidencia:|\*\*Esperado:\*\*|\*\*Obtenido:\*\*|\*\*Hip\u00f3tesis:\*\*|\*\*Ruta y acci\u00f3n:\*\*|\*\*Reproducci\u00f3n:\*\*)/g, '\n  - $1');
}
