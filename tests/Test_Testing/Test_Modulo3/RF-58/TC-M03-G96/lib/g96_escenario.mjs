import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
export const PRESUPUESTO = require('./g96_presupuesto.cjs');
export const CASO = 'TC-M03-187';
export const ORACULO = 'El estado de conectividad presentado por el monitoreo utiliza exclusivamente uno de los valores definidos por RF-58 (ONLINE, OFFLINE o SIN_SEÑAL); no se exponen valores diferentes al catálogo establecido.';
export const CATALOGO = ['ONLINE', 'OFFLINE', 'SIN_SEÑAL'];
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G96', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { [CASO]: { API: ['API-187-01'] } },
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_en_run,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos },
});
export function canonico(valor) {
  if (typeof valor !== 'string') return null;
  const v = valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  if (v === 'SIN_SENAL') return 'SIN_SEÑAL';
  return ['ONLINE', 'OFFLINE'].includes(v) ? v : null;
}
export function clasificar(observado) {
  const { paginas = [], agotado = false, paginasCompletas = true, error = null } = observado;
  if (!paginas.length && error === 'SIN_RESPUESTA') return { estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta del dashboard' };
  const validas = paginas.filter(p => p.http === 200 && p.eco && Array.isArray(p.sensores));
  const valores = validas.flatMap(p => p.sensores.map(s => Object.hasOwn(s, 'estado_conectividad') ? s.estado_conectividad : '[AUSENTE]'));
  const fuera = valores.filter(v => !canonico(v));
  if (fuera.length) return { estado: 'RECHAZADO', motivo: `Valor fuera del catálogo en respuesta 200 con eco: ${[...new Set(fuera.map(String))].join(', ')}` };
  if (paginas.some(p => p.http >= 500) || error === 'HTTP_5XX') return { estado: 'BLOQUEADO', motivo: 'Dashboard respondió 5xx' };
  if (error === 'SIN_RESPUESTA') return { estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta en una página pendiente' };
  if (error || paginas.some(p => p.http === 200 && (!p.eco || !Array.isArray(p.sensores))))
    return { estado: 'NO_CONCLUYENTE', motivo: `Evidencia API incompleta o eco ausente: ${error ?? 'FORMATO_O_ECO'}` };
  if (!paginasCompletas) return { estado: 'BLOQUEADO', motivo: 'Paginación por unidad incompleta dentro del presupuesto' };
  const presentes = new Set(valores.map(canonico));
  if (CATALOGO.every(v => presentes.has(v)) && !agotado)
    return { estado: 'APROBADO', motivo: 'Tres condiciones observadas; todos los valores pertenecen al catálogo' };
  return { estado: 'BLOQUEADO', motivo: `Cobertura de datos incompleta: faltan ${CATALOGO.filter(v => !presentes.has(v)).join(', ') || 'páginas pendientes'}` };
}
