// Solo acredita la estimación si hay una marca explícita y un vínculo con el precio 492.
export function evaluarEstimacion1644({calculos=[],auditoria=[],avisos=[],cierre={},congelados=[],precio492}){
  const usado=x=>Number(x?.id_precio_mercado)===492&&Number(x?.precio_unitario)===Number(precio492);
  const calculo=calculos.find(x=>Number(x.id_activo_biologico)===1644&&x.tiene_valor_estimado===true&&Number(x.precio_unitario)===Number(precio492));
  const congelado=congelados.find(x=>Array.isArray(x.id_especie)?Number(x.id_especie[0])===544&&x.id_especie[1]===true:Number(x.id_especie)===544&&x.tiene_valor_estimado===true);
  const auditoriaEstimada=auditoria.find(x=>x.tipo_evento==='MEDICION_CON_ESTIMACION'&&Number(x.id_activo_biologico)===1644&&usado(x.payload_evento?.precio_usado));
  const procesado=Number(cierre.activos_procesados)>0&&(!Array.isArray(cierre.activos_excluidos)||!cierre.activos_excluidos.some(x=>Number(x.id_activo_biologico)===1644));
  const respuestaEstimada=procesado&&Array.isArray(cierre.activos_estimados)&&cierre.activos_estimados.some(x=>Number(x?.id_activo_biologico??x)===1644)&&usado(congelado);
  const alertaEstimada=procesado&&avisos.some(x=>/PRECIO_ESTIMADO|precio estimado/i.test(x.texto??'')&&/1644|A-1644|Lote 1644/i.test(x.texto??''))&&usado(congelado);
  return {acreditada:Boolean(calculo||auditoriaEstimada||respuestaEstimada||alertaEstimada),vias:{calculo:Boolean(calculo),auditoria:Boolean(auditoriaEstimada),respuesta:Boolean(respuestaEstimada),alerta:Boolean(alertaEstimada)},auditoria_sin_variacion:auditoria.some(x=>x.tipo_evento==='MEDICION_SIN_VARIACION'&&Number(x.id_activo_biologico)===1644),precio_congelado_492:usado(congelado),activos_procesados:cierre.activos_procesados??null};
}
