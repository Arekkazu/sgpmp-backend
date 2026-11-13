const texto=x=>String(x?.textContent??x??'').replace(/\s+/g,' ').trim();
const visible=x=>!!x&&x.getClientRects().length>0&&x.getAttribute('aria-hidden')!=='true';
function inspeccionarVista(root,panel,esperado){
  const nodos=s=>[...root.querySelectorAll(s)].filter(visible);
  const encabezados=nodos('h1,h2,h3,h4,[role="heading"]').map(texto).filter(Boolean);
  const tablas=nodos('table,[role="table"]').map(t=>({titulo:texto(t.querySelector('caption'))||texto(t.previousElementSibling),encabezados:[...t.querySelectorAll('th,[role="columnheader"]')].map(texto),filas:[...t.querySelectorAll('tbody tr,[role="row"]')].filter(visible).map(texto)}));
  const controles=nodos('button,input,[role="button"],[role="checkbox"],[role="radio"]').map(x=>({tipo:x.getAttribute('role')||x.type||x.tagName.toLowerCase(),texto:texto(x.closest('label'))||texto(x),aria_label:x.getAttribute('aria-label')||'',title:x.title||'',name:x.name||'',checked:!!x.checked,deshabilitado:!!x.disabled}));
  const table=panel==='027'?tablas.find(t=>/trazabilidad incompleta/i.test(t.titulo)):tablas.find(t=>/activo/i.test(t.encabezados.join(' '))&&/especie/i.test(t.encabezados.join(' '))&&/decisión/i.test(t.encabezados.join(' ')));
  const fila=table?.filas.find(x=>panel==='027'?/Línea 17/i.test(x)&&x.includes(String(esperado.activos[0])):x.includes(String(esperado.activos[0]?.id??esperado.activos[0])));
  const nombre=x=>[x.texto,x.aria_label,x.title].join(' ');
  const radios=controles.filter(x=>x.tipo==='radio'&&x.name==='sin-precio-1644');
  const excluir=radios.some(x=>/Excluir de este cierre/i.test(nombre(x)));
  const estimar=radios.some(x=>/Medir con el último precio conocido, como estimación/i.test(nombre(x)));
  const casilla=controles.some(x=>x.tipo==='checkbox'&&/Autorizo excluir del comprobante/i.test(nombre(x)));
  const cerrar=controles.find(x=>/Cerrar período/i.test(nombre(x)));
  const pausa=/El cierre espera tu decisión/i.test(texto(root))&&controles.some(x=>/Cancelar el cierre/i.test(nombre(x)));
  const faltas=[];
  if(panel==='025'){const contenido=texto(root);if(!/Precondiciones para cerrar/i.test(contenido)||!new RegExp(`\\b${esperado.conteo}\\b`).test(contenido))faltas.push(`precondición de precios con conteo ${esperado.conteo}`);if(!contenido.includes(`${esperado.activos[0].identificador} (${esperado.activos[0].especie})`))faltas.push(`${esperado.activos[0].identificador} (${esperado.activos[0].especie})`);}
  if(panel==='025'&&fila&&!fila.includes(String(esperado.activos[0].especie)))faltas.push(`especie ${esperado.activos[0].especie} en fila`);
  if(!table)faltas.push(panel==='027'?'tabla de trazabilidad incompleta':'tabla Activos sin precio vigente');
  if(!fila)faltas.push(panel==='027'?'Línea 17, activo 944 y eslabón faltante':'fila del activo 1644');
  if(panel==='027'){const etiquetas={lecturas_nic41:'Lecturas IoT aptas',origen:'Registro de origen',precio_documentado:'Precio con evidencia',evento_m02:'Evento del activo',evento_sanitario:'Evento sanitario',cierre:'Cierre del período'};if(!esperado.eslabones.every(e=>fila?.toLowerCase().includes((etiquetas[e]??String(e)).toLowerCase())))faltas.push(`eslabón ${esperado.eslabones.join(', ')}`);if(!casilla)faltas.push('Autorizo excluir del comprobante');}
  else {if(!excluir)faltas.push('Excluir de este cierre');if(panel==='026'&&!estimar)faltas.push('Medir con el último precio conocido, como estimación');if(panel==='025'&&!/Sin precio de mercado vigente para su especie/i.test(fila||''))faltas.push('Sin precio de mercado vigente para su especie');}
  if(!cerrar)faltas.push('Cerrar período');else if(!cerrar.deshabilitado)faltas.push('Cerrar período deshabilitado antes de decidir');
  return {resumen_dom:{encabezados,tablas,controles},controles_citados:controles.map(nombre).filter(Boolean),lista_completa:!!fila,decision_por_activo:excluir&&(panel==='025'||estimar),casilla_autorizacion:casilla,boton_deshabilitado:!!cerrar?.deshabilitado,pausa,diagnostico:faltas.length?`Falta: ${faltas.join('; ')}. Encontrado: ${table?JSON.stringify(table):'sin tabla'}; controles ${controles.map(nombre).join('; ')}`:null,faltas};
}
function elementosVista(root,panel){
 const visibles=[...root.querySelectorAll('table,input[type="checkbox"],input[type="radio"],button')].filter(visible);
 const elementos=visibles.filter(x=>x.tagName==='TABLE'?(panel==='027'?/trazabilidad incompleta/i.test(texto(x.querySelector('caption'))):/Activo.*Especie.*Motivo.*Decisión/i.test(texto(x.querySelector('thead')))):/Cerrar período|Cancelar cierre|Autorizo excluir|Excluir de este cierre|Medir con el último precio/i.test(texto(x.closest('label'))||texto(x)));
 return elementos.map((elemento,i)=>({elemento,nombre:`G43-UI-${panel}-${elemento.tagName==='TABLE'?'tabla':elemento.type||'boton'}-${i+1}.png`}));
}
module.exports={inspeccionarVista,elementosVista};
