// Límite único del escenario G96; reflejar estos valores en la SOL futura.
module.exports = Object.freeze({
  unidades_conocidas: [1, 268, 337],
  unidades_adicionales: 3,
  fincas_descubrimiento: 2,
  lecturas_descubrimiento: 3, // fincas + dos listados de infraestructuras
  paginas_dashboard: 12,
  por_pagina: 50,
  solicitudes_en_run: 15, // 3 descubrimientos + 12 páginas
  margen_cierre: 1,
  duracion_segundos: 600,
});
