import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluarEvento, CAPACIDADES, rutaHistorial, identidadJwt } from '../lib/g127_escenario.mjs';

test('oráculo de evento completo y ausencias pertinentes', () => {
  const op = { idUsuario: 7, idRol: 4, sensorId: 6, porPagina: 37, inicio: '2026-10-20',
    fin: '2026-10-27', registros: 3, desde: '2026-10-27T00:00:00Z',
    hasta: '2026-10-27T00:01:00Z' };
  const e = { id_evento: 'e', id_usuario: 7, tipo_evento: 'HISTORIAL_CONSULTADO',
    fecha_hora: '2026-10-27T00:00:30Z', accion_detallada: { id_rol: 4,
      filtros: { sensor_id: 6, fecha_inicio: op.inicio, fecha_fin: op.fin },
      por_pagina: 37, registros_devueltos: 3, exportado: false } };
  assert.equal(evaluarEvento([e], op).estado, 'APROBADO');
  const sinRango = structuredClone(e); delete sinRango.accion_detallada.filtros.fecha_fin;
  assert.match(evaluarEvento([sinRango], op).motivo, /rango temporal/);
  const sinCantidad = structuredClone(e); delete sinCantidad.accion_detallada.registros_devueltos;
  assert.match(evaluarEvento([sinCantidad], op).motivo, /cantidad/);
  const sinExportado = structuredClone(e); delete sinExportado.accion_detallada.exportado;
  assert.match(evaluarEvento([sinExportado], op).motivo, /si se exportó/);
  const rolIncorrecto = structuredClone(e); rolIncorrecto.accion_detallada.id_rol = 1;
  assert.match(evaluarEvento([rolIncorrecto], op).motivo, /rol/);
  assert.equal(evaluarEvento([], op).estado, 'RECHAZADO');
});
test('capacidades API y filtro distintivo', () => {
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias,
    { 'TC-M03-256': { API: ['API-256-01'] } });
  assert.match(rutaHistorial({ inicio: '2026-10-20', fin: '2026-10-27', sensorId: 6 }, 37),
    /por_pagina=37/);
  assert.deepEqual(identidadJwt('sin.jwt.valido'), { id: null, rol: null });
});
