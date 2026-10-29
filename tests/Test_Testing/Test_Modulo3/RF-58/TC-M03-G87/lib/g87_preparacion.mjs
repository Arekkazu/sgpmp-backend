// Decisiones puras del RUN G87. No acceden a TEST ni crean evidencias.
export function valoresS1(umbral, fisico) {
  const [fisMin, fisMax] = fisico ?? [];
  const { min, max, id } = umbral;
  if (![min, max, fisMin, fisMax].every(Number.isFinite) || min > max || fisMin > fisMax)
    throw new Error('BLOQUEO_DATOS: umbral de S1 o rango físico no verificable.');
  if (!(min <= 25 && 25 <= max && fisMin <= 25 && 25 <= fisMax))
    throw new Error(`BLOQUEO_DATOS: umbral ${id} o rango físico no admite el valor 25 de TC-M03-177.`);
  const fuera = max < fisMax ? Math.min(max + 1, fisMax) : min > fisMin ? Math.max(min - 1, fisMin) : null;
  if (fuera === null)
    throw new Error(`BLOQUEO_DATOS: umbral ${id} y rango físico no permiten FUERA_DE_RANGO sin ERROR_SENSOR.`);
  const validosMin = Math.max(min, fisMin);
  return { v_a1: Math.max(validosMin, 23), v_a2: Math.max(validosMin, 24), v_a3: 25, v_fuera: fuera };
}

export function uiHabilitada(comprobaciones, caso, ids, hostRun, sensorVisible) {
  if (!hostRun || !sensorVisible) return false;
  const cs = comprobaciones.filter((x) => x.caso === caso);
  return ids.every((id) => {
    const pre = cs.filter((x) => x.tipo === 'PRE' && x.fuente === 'API' && x.id === id);
    return pre.length > 0 && pre.every((x) => x.ok === true);
  }) && cs.filter((x) => x.tipo === 'SETUP').every((x) => x.ok === true);
}

export function comprobacionesUiFaltantes(comprobaciones, caso, ids) {
  return ids.filter((id) => !comprobaciones.some((x) => x.caso === caso && x.fuente === 'UI' && x.id === id));
}

export function estadoGrupoG87(casos) {
  const estados = Object.values(casos).map((x) => x.estado);
  if (!estados.length || estados.some((x) => !['APROBADO', 'RECHAZADO'].includes(x))) return 'PARCIAL';
  return estados.includes('RECHAZADO') ? 'RECHAZADO' : 'APROBADO';
}

export function indicadorCalibracion(obj, ruta = '') {
  if (!obj || typeof obj !== 'object') return null;
  for (const [campo, valor] of Object.entries(obj)) {
    const rutaCampo = ruta ? `${ruta}.${campo}` : campo;
    if (typeof valor === 'string' && /estado|error|calibra|diagn[oó]stico|mensaje|detalle|condici[oó]n/i.test(campo)
      && /ERROR_CALIBRACION|requiere calibraci[oó]n|error de calibraci[oó]n/i.test(valor))
      return { campo: rutaCampo, valor: valor.slice(0, 120) };
    const anidado = indicadorCalibracion(valor, rutaCampo);
    if (anidado) return anidado;
  }
  return null;
}
