import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
export const PRESUPUESTO = require('./g96_presupuesto.cjs');
export const CASO = 'TC-M03-187';
export const CATALOGO = ['ACTIVO', 'SIN_SEÑAL', 'BUFFER_ACTIVO', 'INACTIVO', 'EN_MANTENIMIENTO'];
export const ORACULO = 'El dashboard presenta los cinco estados de conectividad de RF-60, fase 7 y postcondición 3: ACTIVO, SIN_SEÑAL, BUFFER_ACTIVO, INACTIVO y EN_MANTENIMIENTO.';
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G96', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { [CASO]: { API: ['API-187-01', 'API-187-02'] } },
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_en_run,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos },
});
export const canonico = valor => typeof valor === 'string' && CATALOGO.includes(valor) ? valor : null;
export function clasificar({ paginas = [], dispositivos = {}, disponibles = {}, error = null, paginasCompletas = true } = {}) {
  const validas = paginas.filter(p => p.http === 200 && p.eco && Array.isArray(p.sensores));
  const sensores = validas.flatMap(p => p.sensores.map(s => ({ ...s, unidad: p.unidad, rol: p.rol })));
  const fuera = sensores.filter(s => !canonico(s.estado_conectividad) && s.estado_conectividad !== 'DESCONOCIDO');
  const catalogo = fuera.length ? { estado: 'RECHAZADO', motivo: `Estado fuera del catálogo RF-60: ${[...new Set(fuera.map(s => String(s.estado_conectividad)))].join(', ')}` }
    : !validas.length || error || !paginasCompletas || paginas.some(p => p.http !== 200 || !p.eco || !Array.isArray(p.sensores))
      ? { estado: 'NO_CONCLUYENTE', motivo: `Lectura incompleta: ${error ?? 'HTTP_PAGINACION_O_ECO'}` }
      : { estado: 'APROBADO', motivo: 'Todos los estados observados pertenecen al catálogo; DESCONOCIDO se informa aparte' };
  const cobertura = Object.fromEntries(CATALOGO.map(estado => {
    const candidatos = dispositivos[estado] ?? [];
    if (!candidatos.length) return [estado, { estado: 'NO_CONCLUYENTE', motivo: disponibles[estado]
      ? 'Ningún dispositivo de este estado tuvo sensores propios visibles en las páginas inspeccionadas, o se agotó el presupuesto de canarios'
      : 'Sin dispositivo en el estado; no puede construirse cobertura sin escrituras; no se crean datos' }];
    const cotejos = candidatos.map(d => ({ d, filas: sensores.filter(s => s.unidad === d.id_infraestructura
      && s.rol === d.rol && s.id_dispositivo_iot === d.id_dispositivo_iot) }));
    const discrepancia = cotejos.find(x => x.filas.some(s => s.estado_conectividad !== estado));
    if (discrepancia) return [estado, { estado: 'RECHAZADO', motivo: `Dispositivo ${discrepancia.d.id_dispositivo_iot} en ${estado}; dashboard ${[...new Set(discrepancia.filas.map(s => String(s.estado_conectividad)))].join(', ')}`, dispositivo: discrepancia.d.id_dispositivo_iot, area: discrepancia.d.id_infraestructura, rol: discrepancia.d.rol, sensores_cotejados: discrepancia.filas.length }];
    const visible = cotejos.find(x => x.filas.length);
    return [estado, visible ? { estado: 'APROBADO', motivo: `Dispositivo ${visible.d.id_dispositivo_iot} y ${visible.filas.length} sensor(es) concordantes`, dispositivo: visible.d.id_dispositivo_iot, area: visible.d.id_infraestructura, rol: visible.d.rol, sensores_cotejados: visible.filas.length }
      : { estado: 'NO_CONCLUYENTE', motivo: 'No hay sensor asociado visible para el rol consultado en las áreas candidatas' }];
  }));
  const cobertura_detalle = CATALOGO.flatMap(estado => (dispositivos[estado] ?? []).map(d => ({
    estado, dispositivo: d.id_dispositivo_iot, area: d.id_infraestructura, rol: d.rol,
    sensores_cotejados: sensores.filter(s => s.unidad === d.id_infraestructura && s.rol === d.rol
      && s.id_dispositivo_iot === d.id_dispositivo_iot).length,
  })));
  const fallos = Object.values(cobertura).filter(x => x.estado === 'RECHAZADO');
  const pendientes = Object.values(cobertura).filter(x => x.estado === 'NO_CONCLUYENTE');
  const estado = catalogo.estado === 'RECHAZADO' || fallos.length ? 'RECHAZADO'
    : catalogo.estado === 'APROBADO' && !pendientes.length ? 'APROBADO' : 'NO_CONCLUYENTE';
  return { estado, motivo: catalogo.estado === 'RECHAZADO' ? catalogo.motivo : fallos.length ? fallos.map(x => x.motivo).join('; ')
    : catalogo.estado !== 'APROBADO' ? catalogo.motivo : pendientes.length ? `Cobertura pendiente: ${CATALOGO.filter(x => cobertura[x].estado === 'NO_CONCLUYENTE').join(', ')}` : 'Cinco estados cotejados con dispositivo y sensores visibles', catalogo, cobertura, cobertura_detalle,
    desconocido: sensores.filter(s => s.estado_conectividad === 'DESCONOCIDO').length,
    desconocido_areas: [...new Set(sensores.filter(s => s.estado_conectividad === 'DESCONOCIDO').map(s => s.unidad))] };
}
