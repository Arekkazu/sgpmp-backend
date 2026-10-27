function elegirUnidad(body) {
  const unidades = Array.isArray(body?.resumen_unidades) ? body.resumen_unidades : [];
  const sensores = Array.isArray(body?.sensores) ? body.sensores : [];
  if (!unidades.length) return { id: null, e7_riesgo: false, motivo: null,
    bloqueo_datos: 'RESUMEN_UNIDADES_VACIO' };
  const elegibles = unidades.filter(u => Number(u.total_sensores) > 0);
  const segura = elegibles.find(u => {
    const recibidos = sensores.filter(s => Number(s.id_infraestructura) === Number(u.id_infraestructura));
    return recibidos.length === Number(u.total_sensores)
      && !recibidos.some(s => String(s.estado_semaforo).toUpperCase() === 'GRIS' && !s.dato_desactualizado);
  });
  if (segura) return { id: segura.id_infraestructura, e7_riesgo: false,
    motivo: 'UNIDAD_COMPLETA_SIN_GRIS_VIGENTE_EN_PRIMERA_PAGINA', bloqueo_datos: null };
  const primera = elegibles[0];
  if (primera) return { id: primera.id_infraestructura, e7_riesgo: true,
    motivo: 'NINGUNA_UNIDAD_ACREDITABLE_EN_PRIMERA_PAGINA; LECTURAS_FILTRADAS_PUEDEN_ACTIVAR_CORREO_E7',
    bloqueo_datos: null };
  return { id: null, e7_riesgo: false, motivo: 'RESUMEN_SIN_UNIDAD_CON_SENSORES', bloqueo_datos: null };
}

module.exports = { elegirUnidad };
