// Servidor local y espía para LOCAL_SMOKE; recibe datos y paneles desde un escenario del grupo.
import http from 'node:http';

export async function simuladorBase(escenario,{ausentes=[],demoraOpcionMs=0,valueNoNumerico=[],pausa=false,pausaSoloCancelar=false}={}){
  const peticiones=[];
  const paneles=escenario.paneles;
  const titulares={A:'111111111',G:'777777777',D:'444444444'};
  const periodos=Object.keys(paneles).filter(id=>!ausentes.includes(Number(id))).map(id=>({
    id_periodo_contable:Number(id),numero_id_tributaria:Number(id)===8?titulares.A:titulares.G,estado:'ABIERTO',
    fecha_inicio:Number(id)===267?'2026-12-01':'2026-11-01',fecha_fin:Number(id)===267?'2026-12-31':'2026-11-30'
  }));
  const html=`<!doctype html><html lang="es"><head><style>main{height:360px;overflow-y:auto}main section{min-height:450px}#decision-pausa{min-height:420px}article{padding:24px}</style></head><body>
    <form id="login"><input type="email"><input type="password"><button type="submit">Entrar</button></form>
    <main><h1>Finanzas</h1><nav>Cierre</nav>
    <label for="fin-titular">Titular</label><select id="fin-titular">
      <option value="${titulares.D}">Agropecuaria El Rosal S.A.S. · NIT ${titulares.D}</option>
      <option value="${titulares.A}">Titular A S.A.S. · NIT ${titulares.A}</option>
      <option value="${titulares.G}">Titular G S.A.S. · NIT ${titulares.G}</option>
    </select>
    <label for="fin-periodo">Período contable</label><select id="fin-periodo" disabled></select>
    <h2 id="titulo-cierre">Cierre del período</h2><div id="tarjeta-titular">Titular tributario NIT</div>
    <section aria-labelledby="cierre-pre"><h3 id="cierre-pre">Precondiciones para cerrar</h3><p>0 de 9 completas</p><div>Comprobantes NIC 41</div><div>Períodos cerrados</div></section><div id="decision-pausa"></div></main>
    <script>
      const paneles=${JSON.stringify(paneles)}, demora=${JSON.stringify(demoraOpcionMs)}, noNumerico=${JSON.stringify(valueNoNumerico)}, pausa=${JSON.stringify(pausa)}, pausaSoloCancelar=${JSON.stringify(pausaSoloCancelar)};
      const titular=document.querySelector('#fin-titular'),selector=document.querySelector('#fin-periodo');
      const mes=fecha=>{const [a,m]=fecha.split('-');const s=new Intl.DateTimeFormat('es-CO',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(Number(a),Number(m)-1,1)));return s[0].toUpperCase()+s.slice(1);};
      document.querySelector('#login').onsubmit=async e=>{e.preventDefault();await fetch('/sesiones/',{method:'POST'});};
      async function cargarPeriodos(){
        selector.disabled=true;selector.innerHTML='';
        const respuesta=await fetch('/finanzas/periodos?numero_id_tributaria='+encodeURIComponent(titular.value)),periodos=await respuesta.json();
        setTimeout(()=>{selector.innerHTML=periodos.map(p=>'<option data-id="'+p.id_periodo_contable+'" value="'+(noNumerico.includes(p.id_periodo_contable)?'p-'+p.id_periodo_contable:p.id_periodo_contable)+'">'+mes(p.fecha_inicio)+' · '+p.estado+'</option>').join('');selector.disabled=periodos.length===0;},demora);
      }
      titular.onchange=cargarPeriodos;
      selector.onchange=async()=>{
        const id=selector.selectedOptions[0]?.dataset.id;
        if(!paneles[id])return;
        document.querySelector('#titulo-cierre').textContent='Cierre del período — '+mes(id==='267'?'2026-12-01':'2026-11-01');
        document.querySelector('#tarjeta-titular').textContent='Titular tributario NIT '+titular.value;
        await fetch('/finanzas/periodos/'+id+'/prevalidacion');
        const tarjeta='<article><h3>El cierre espera tu decisión</h3><p>El cierre está detenido hasta que autorices las exclusiones o lo canceles</p><button>Cancelar el cierre</button></article>';
        const titulo=id==='8'?'Trazabilidad de las líneas de asiento':'Precios de mercado vigentes';
        document.querySelector('section').innerHTML=pausa?'':'<h3 id="cierre-pre">Precondiciones para cerrar</h3><p>8 de 9 completas</p><div>1 activo sin precio: A-1644 (Bovino)</div>'+paneles[id].html;
        document.querySelector('#decision-pausa').innerHTML=pausa?tarjeta:'';
        if(!pausa){const area=document.querySelector('section'),cerrar=[...area.querySelectorAll('button')].find(x=>x.textContent.includes('Cerrar período'));area.querySelectorAll('input[type=radio],input[type=checkbox]').forEach(x=>x.onchange=()=>{cerrar.disabled=false;});const no=[...area.querySelectorAll('button')].find(x=>x.textContent.includes('Cancelar cierre (No)'));if(no)no.onclick=()=>{area.querySelectorAll('input').forEach(x=>x.checked=false);cerrar.disabled=true;};}
      };
      window.addEventListener('popstate',cargarPeriodos);
      if(location.pathname.endsWith('/finanzas/cierre'))cargarPeriodos();
    </script></body></html>`;
  const server=http.createServer((req,res)=>{
    peticiones.push({metodo:req.method,ruta:req.url});
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{};
    if(req.url==='/login'||req.url==='/'||req.url==='/finanzas/cierre'){
      res.writeHead(200,{'content-type':'text/html',...eco});res.end(html);return;
    }
    if(req.url.startsWith('/finanzas/periodos?')){
      const numero=new URL(req.url,'http://localhost').searchParams.get('numero_id_tributaria');
      res.writeHead(200,{'content-type':'application/json',...eco});
      res.end(JSON.stringify(periodos.filter(p=>p.numero_id_tributaria===numero)));return;
    }
    const match=req.url.match(/^\/finanzas\/periodos\/(\d+)\/prevalidacion$/);
    if(match&&paneles[match[1]]){
      res.writeHead(200,{'content-type':'application/json',...eco});
      res.end(JSON.stringify(paneles[match[1]].prevalidacion));return;
    }
    res.writeHead(404,eco);res.end();
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return{url:`http://127.0.0.1:${server.address().port}/`,peticiones,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
