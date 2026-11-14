'use strict';

// Fuente única del límite operativo del ejecutor y de la documentación G120.
const presupuesto = Object.freeze({
  solicitudes_directas: 72,
  solicitudes_newman: 1,
  margen_cierre: 2,
  duracion_segundos: 600,
  inactividad_maxima_segundos: 180,
  inactividad_guardia_segundos: 170,
  dispositivos: 12,
  sensores_por_dispositivo: 3,
  unidades_dashboard: 8,
  unidades_conocidas: Object.freeze([1, 268, 337]),
  historiales_semilla: 36,
  timeout_descubrimiento_ms: 20000,
  desglose_maximo: Object.freeze({
    openapi: 1, logins: 2, listados_semilla: 3,
    dispositivos: 12, dashboards_semilla: 8, historiales_semilla: 36, historial_basal: 1,
    ingestas: 5, auditoria: 2, cierre_y_rollback: 2,
  }),
});

module.exports = presupuesto;
if (require.main === module) console.log(JSON.stringify(presupuesto, null, 2));
