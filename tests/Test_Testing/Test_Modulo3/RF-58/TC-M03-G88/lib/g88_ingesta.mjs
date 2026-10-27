// Todas las marcas se calculan antes de abrir la transacción del sandbox.
// 120 s cubren desfase de reloj; 5 s separan las 11 lecturas posibles.
export const MARGEN_RELOJ_MS = 120_000;
export const PASO_INGESTA_MS = 5_000;
export const INGESTAS_POR_CASO = Object.freeze({
  'TC-M03-169': 3, 'TC-M03-170': 4, 'TC-M03-171': 2,
  'TC-M03-180': 1, 'TC-M03-266': 1,
});

export function planTemporalIngestas(casos, inicioRun = new Date().toISOString()) {
  const inicio = Date.parse(inicioRun);
  if (!Number.isFinite(inicio)) throw new Error('INICIO_RUN_INVALIDO');
  const claves = casos.flatMap((caso) => Array.from(
    { length: INGESTAS_POR_CASO[caso] ?? 0 }, (_, indice) => `${caso}:${indice}`));
  const ancla = inicio - MARGEN_RELOJ_MS;
  return { inicio_run: new Date(inicio).toISOString(), ancla: new Date(ancla).toISOString(),
    margen_reloj_segundos: MARGEN_RELOJ_MS / 1000, paso_ingesta_segundos: PASO_INGESTA_MS / 1000,
    por_ingesta: Object.fromEntries(claves.map((clave, i) =>
      [clave, new Date(ancla - (claves.length - i) * PASO_INGESTA_MS).toISOString()])) };
}

// Cuerpo único para las ingestas de 169–171, 180 y 266.
export function construirCuerpoIngesta({ deviceId, sensorId, tipoVariable, valor, unidad,
  timestampCaptura, serial }) {
  if (typeof serial !== 'string' || !serial.trim()) throw new Error('SERIAL_INGESTA_AUSENTE');
  if (!Number.isFinite(Date.parse(timestampCaptura))) throw new Error('TIMESTAMP_INGESTA_AUSENTE');
  return { device_id: deviceId, sensor_id: sensorId, tipo_variable: tipoVariable,
    valor, unidad, timestamp_captura: timestampCaptura, serial,
    nivel_bateria: 81, calidad_senal_rssi: -71, calidad_senal_snr: 7.5 };
}

export function cuerpoOpcionalNewman({ soloUmbrales = false, skipIngesta = false, parametros }) {
  return soloUmbrales || skipIngesta ? '' : JSON.stringify(construirCuerpoIngesta(parametros));
}
