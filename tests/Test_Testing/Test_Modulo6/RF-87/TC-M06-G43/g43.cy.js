const {clasificarIntercepcion,evaluarSeleccionPeriodo,requiereCambioExplicito,mesPeriodo,opcionTitular,opcionPeriodo,selectorPorEtiqueta}=require('./lib/intercepcion.cjs');
const {inspeccionarVista,elementosVista}=require('./lib/vista_cierre.cjs');
const env=k=>Cypress.env(k),API=String(env('API_BASE')||'').replace(/\/+$/,''),FRONT=String(env('FRONT_BASE')||'').replace(/\/+$/,'');
const RUN=String(env('RUN_ID')||''),DIR=String(env('ARTIFACTS_DIR')||''),PANEL=String(env('PANEL')||''),EXPECTED=typeof env('EXPECTED')==='string'?JSON.parse(env('EXPECTED')):env('EXPECTED')||{};
const trial=env('LOCAL_SMOKE')==='SI';
const loopback=u=>{try{const x=new URL(u);return x.protocol==='http:'&&['127.0.0.1','localhost'].includes(x.hostname)&&Boolean(x.port)&&x.pathname==='/';}catch{return false;}};
const numero=String(env('NUMERO_ID_TRIBUTARIA')||''),alias=PANEL==='027'?'TITULAR_A':'TITULAR_G';
const valid=/^RUN-G\d+-V\d+-\d{8}-\d{6}$/.test(RUN)&&(trial?loopback(API)&&loopback(FRONT):/^https:\/\/(?:www\.)?api\.inmero\.co\/api-sgpmp-test$/.test(API)&&/^https:\/\/(?:www\.)?api\.inmero\.co\/sigab-test$/.test(FRONT))&&['025','026','027'].includes(PANEL)&&DIR&&env('PROD_LOGIN_TOKEN')&&env('SANDBOX_SECRET')&&numero;
const periodo=Number(env('PERIODO')||({'025':266,'027':8}[PANEL]||0)),acta={caso:`TC-M06-${PANEL}`,id:`G43-UI-${PANEL}-01`,estado:'NO_CONCLUYENTE',lista_completa:false,decision_por_activo:false,total_prevalidacion:null,controles:[],captura:false,peticiones:[],post_prohibidos:[],titular_alias:alias,titular_seleccionado:false,consultas_periodos:[],opciones_titular:[],opciones_periodo:[],respuestas_periodos:[]};
const textoSeguro=x=>String(x||'').replace(/\s*·?\s*NIT\b.*$/i,'').trim();
let cola=Promise.resolve();
function interceptar(){cy.intercept({url:/^https?:\/\//,middleware:true},req=>{
  const {destino,ruta}=clasificarIntercepcion(req.url,req.method,API,FRONT,trial);
  if(destino==='FRONTAL'){req.continue();return;}
  if(destino==='BLOQUEADO'){req.reply({forceNetworkError:true});return;}
  const row={metodo:req.method,ruta,http:null,eco:false};
  acta.peticiones.push(row);
  if(acta.peticiones.length>40){req.reply({forceNetworkError:true});return;}
  if(req.method==='GET'&&ruta==='/__sonda__'){
    req.alias='sonda';row.http=200;row.eco=true;
    req.reply({statusCode:200,headers:{'x-test-run-id':RUN},body:{interceptado:true}});return;
  }
  if(req.method==='POST'&&ruta==='/sesiones/'){
    req.alias='login';row.http=200;row.eco=true;
    req.reply({statusCode:200,headers:{'x-test-run-id':RUN},body:{token:env('PROD_LOGIN_TOKEN')}});return;
  }
  if(!['GET','OPTIONS'].includes(req.method)){if(req.method==='POST'&&/^\/finanzas\/periodos\/\d+\/(cierre|cierre\/cancelacion)$/.test(ruta)){acta.post_prohibidos.push(ruta);acta.estado='NO_CONCLUYENTE';acta.motivo=`ERROR_QA_POST_CIERRE_DISPARADO: ${ruta}`;}req.reply({forceNetworkError:true});return;}
  if(ruta==='/finanzas/periodos'){
    req.alias='periodos';
    const u=new URL(req.url),q=u.searchParams.get('numero_id_tributaria');
    acta.consultas_periodos.push({query:{numero_id_tributaria:q===null?null:q===numero?alias:'OTRO'},otros_parametros:[...u.searchParams.keys()].filter(k=>k!=='numero_id_tributaria')});
  }
  if(ruta===`/finanzas/periodos/${periodo}/prevalidacion`)req.alias='prevalidacion';
  let release;const turn=cola;cola=new Promise(resolve=>release=resolve);
  return turn.then(()=>{
    req.headers['X-Test-Run-Id']=RUN;req.headers['X-Sandbox-Secret']=env('SANDBOX_SECRET');
    req.continue(res=>{row.http=res.statusCode;row.eco=res.headers?.['x-test-run-id']===RUN;release();});
  });
});}
describe('G43 panel del Contador',()=>{
  beforeEach(()=>{interceptar();cy.on('fail',error=>{acta.motivo=acta.motivo||String(error.message).replaceAll(numero,'[ID]').replace(/numero_id_tributaria=[^&\s]+/gi,'numero_id_tributaria=[ID]');throw error;});});
  afterEach(()=>{
    cy.get('body').then($b=>{$b[0].querySelectorAll('input,select,header,nav,aside').forEach(x=>x.style.filter='blur(10px)');$b[0].querySelectorAll('*').forEach(x=>{if(x.children.length===0&&/\bNIT\s*\S+/i.test(x.textContent||''))x.style.filter='blur(10px)';});});
    cy.get('body').then($b=>{
      const tramos=elementosVista($b[0].querySelector('main')||$b[0],PANEL);
      acta.capturas_tramos=[];
      tramos.forEach(({elemento,nombre})=>{
        cy.wrap(elemento).scrollIntoView();
        cy.screenshot(nombre.replace(/\.png$/,''),{capture:'viewport',overwrite:true}).then(()=>acta.capturas_tramos.push(nombre));
      });
    });
    cy.then(()=>{acta.captura=acta.capturas_tramos.length>0;cy.writeFile(`${DIR}/G43-UI-${PANEL}.json`,acta);});
  });
  it(`G43-UI-${PANEL}-01`,()=>{
    if(!valid)throw Error('BLOQUEO_ENTORNO_CYPRESS');
    cy.visit(FRONT+'/login');
    cy.window().then(win=>win.fetch(API+'/__sonda__')).then(x=>x.json()).then(x=>expect(x.interceptado).eq(true));
    cy.wait('@sonda');
    cy.get('input[type="email"]').type('g43-ui@local.invalid',{log:false});
    cy.get('input[type="password"]').type('G43LocalDummy123!',{log:false});
    cy.get('button[type="submit"]').click();
    cy.wait('@login');
    cy.window().then(w=>{const base=new URL(FRONT).pathname.replace(/\/+$/,'');w.history.pushState({},'',base+'/finanzas/cierre');w.dispatchEvent(new w.PopStateEvent('popstate'));});
    cy.wait('@periodos',{requestTimeout:10000,responseTimeout:30000});
    cy.get('body').then($b=>{
      const select=selectorPorEtiqueta($b[0],'Titular');
      if(!select){acta.motivo='TITULAR_SELECTOR_AUSENTE';throw Error(acta.motivo);}
      const elegir=elementos=>{
        const opciones=elementos.map(x=>({value:x.value??x.getAttribute('data-value')??x.textContent.trim(),texto:x.textContent.trim()}));
        acta.opciones_titular=opciones.map((x,i)=>x.value===numero?alias:`OPCION_${i+1}`);
        const objetivo=opcionTitular(numero,opciones);
        if(!objetivo){acta.motivo='TITULAR_OBJETIVO_AUSENTE_EN_SELECTOR';throw Error(acta.motivo);}
        if(select.tagName==='SELECT'){
          const yaSeleccionado=select.value===objetivo.value;
          cy.wrap(select).select(objetivo.value,{log:false}).then(()=>{acta.titular_seleccionado=true;});
          if(yaSeleccionado)cy.wrap(select).trigger('change',{log:false});
        }else cy.wrap(elementos[opciones.indexOf(objetivo)]).click({log:false}).then(()=>{acta.titular_seleccionado=true;});
      };
      if(select.tagName==='SELECT')elegir([...select.options]);
      else{cy.wrap(select).click({log:false});cy.get('[role="option"]').then($o=>elegir([...$o]));}
    });
    let listaPeriodos=[],fechaInicio=null;
    cy.wait('@periodos',{requestTimeout:10000,responseTimeout:30000}).then(({request,response})=>{
      expect(response.statusCode).eq(200);expect(response.headers['x-test-run-id']).eq(RUN);
      if(new URL(request.url).searchParams.get('numero_id_tributaria')!==numero){acta.motivo='TITULAR_FILTRO_GET_FINANZAS_PERIODOS_INCORRECTO';throw Error(acta.motivo);}
      listaPeriodos=Array.isArray(response.body)?response.body:[];
      acta.respuestas_periodos.push(listaPeriodos.map(x=>({id:x.id_periodo_contable,estado:x.estado,fecha_inicio:x.fecha_inicio,fecha_fin:x.fecha_fin})));
      fechaInicio=listaPeriodos.find(x=>Number(x.id_periodo_contable)===periodo)?.fecha_inicio;
    });
    cy.get('body').then($b=>{const select=selectorPorEtiqueta($b[0],'Período contable');if(!select){acta.motivo='PERIODO_CONTABLE_SELECTOR_AUSENTE';throw Error(acta.motivo);}if(select.tagName!=='SELECT')cy.wrap(select).click({log:false});});
    cy.get('body').should($b=>{
      const select=selectorPorEtiqueta($b[0],'Período contable');
      if(!select){acta.motivo='PERIODO_CONTABLE_SELECTOR_AUSENTE';throw Error(acta.motivo);}
      const elementos=select.tagName==='SELECT'?[...select.options]:[...$b[0].querySelectorAll('[role="option"]')];
      acta.opciones_periodo=elementos.map(x=>({value:x.value??x.getAttribute('data-value')??x.textContent.trim(),texto:textoSeguro(x.textContent.trim())}));
      const decision=evaluarSeleccionPeriodo(periodo,listaPeriodos,acta.opciones_periodo,false,fechaInicio);
      if(decision==='AUSENTE_API'){
        acta.motivo=`PERIODO_${periodo}_AUSENTE_EN_GET_FINANZAS_PERIODOS`;
        throw Error(acta.motivo);
      }
      if(decision!=='SELECCIONAR'){
        acta.motivo=`PERIODO_${periodo}_EN_API_SIN_OPCION_EN_SELECTOR`;
        expect(decision,acta.motivo).eq('SELECCIONAR');
      }
      if(select.tagName==='SELECT')expect(select.disabled).eq(false);
      delete acta.motivo;
    });
    cy.get('body').then($b=>{
      const select=selectorPorEtiqueta($b[0],'Período contable'),opcion=opcionPeriodo(periodo,fechaInicio,acta.opciones_periodo);
      if(select.tagName==='SELECT'){
        const cambioExplicito=requiereCambioExplicito(opcion.value,select.value,trial);
        cy.wrap(select).select(opcion.value,{log:false});
        if(cambioExplicito)cy.wrap(select).trigger('change');
      }else{
        const elementos=[...$b[0].querySelectorAll('[role="option"]')];
        const elegido=elementos.find(x=>(x.value??x.getAttribute('data-value')??x.textContent.trim())===opcion.value);
        if(!elegido){acta.motivo=`PERIODO_${periodo}_EN_API_SIN_OPCION_EN_SELECTOR`;throw Error(acta.motivo);}
        cy.wrap(elegido).click({log:false});
      }
    });
    cy.then(()=>{
      cy.contains('h1,h2,h3',`Cierre del período — ${mesPeriodo(fechaInicio)}`,{timeout:10000}).should('be.visible');
    });
    cy.wait('@prevalidacion',{requestTimeout:30000,responseTimeout:30000}).then(({response})=>{
      expect(response.statusCode).eq(200);expect(response.headers['x-test-run-id']).eq(RUN);
      acta.total_prevalidacion=response.body.activos_sin_precio?.length??null;
      const body=response.body,ids=new Set((body.activos_sin_precio||[]).map(x=>Number(x.id_activo_biologico))),lineas=new Set((body.lineas_sin_trazabilidad||[]).map(x=>Number(x.id_linea)));
      const visible=PANEL==="025"?EXPECTED.activos.every(x=>ids.has(Number(x.id))):PANEL==="026"?EXPECTED.sinPrecio.every(x=>ids.has(Number(x))):lineas.has(Number(EXPECTED.linea));
      if(!visible){acta.bloqueo_entorno="DATOS_RUN_NO_VISIBLES_EN_CYPRESS";throw Error("BLOQUEO_ENTORNO_CYPRESS_DATOS_RUN_NO_VISIBLES");}
    });
    cy.contains('Precondiciones para cerrar',{timeout:30000}).should('be.visible');
    cy.contains(/\d+ de \d+ completas/,{timeout:30000}).should('be.visible');
    cy.get('main',{timeout:30000}).should($s=>{const v=inspeccionarVista($s[0],PANEL,EXPECTED);if(!v.resumen_dom.encabezados.length&&!v.resumen_dom.tablas.length&&!v.resumen_dom.controles.length)acta.motivo='ERROR_QA_RESUMEN_DOM_VACIO';expect(v.resumen_dom.encabezados.length).greaterThan(0);});
    cy.get('main').then($s=>{
      const vista=inspeccionarVista($s[0],PANEL,EXPECTED);
      Object.assign(acta,vista);
      acta.estado=vista.pausa||!vista.resumen_dom.encabezados.length?'NO_CONCLUYENTE':vista.faltas.length?'RECHAZADO':'APROBADO';
      if(vista.pausa)acta.motivo='PERIODO_EN_CIERRE_PANEL_EN_PAUSA';
      if(!vista.resumen_dom.encabezados.length)acta.motivo='ERROR_QA_RESUMEN_DOM_VACIO';
      if(acta.peticiones.some(x=>x.http!=null&&!x.eco))acta.estado='NO_CONCLUYENTE';
    });
    cy.then(()=>{
      if(acta.estado!=='APROBADO')return;
      const elegir=PANEL==='027'?'Autorizo excluir del comprobante':PANEL==='026'?'Medir con el último precio conocido, como estimación':'Excluir de este cierre';
      cy.contains('label',elegir).find('input').check({force:true});
      const cerrar=()=>cy.contains('button','Cerrar período');
      const casilla=PANEL!=='027'&&acta.casilla_autorizacion;
      if(casilla){cerrar().should('be.disabled').then(()=>{acta.radio_solo_deshabilitado=true;});cy.contains('label','Autorizo excluir del comprobante las líneas con trazabilidad incompleta').find('input').check({force:true}).then(()=>{acta.casilla_lineas_marcada=true;});}
      cerrar().should('not.be.disabled').then(()=>{acta.decision_habilitada=true;});
      if(PANEL==='025'||PANEL==='026'){
        cy.contains('button','Cancelar cierre (No)').click();
        cerrar().should('be.disabled');
        cy.contains('label',elegir).find('input').should('not.be.checked');
        if(casilla)cy.contains('label','Autorizo excluir del comprobante las líneas con trazabilidad incompleta').find('input').should('not.be.checked');
        cy.then(()=>{acta.cancelacion_desmarca=true;});
      }
    });
    cy.then(()=>{if(acta.post_prohibidos.length){acta.estado='NO_CONCLUYENTE';acta.motivo=`ERROR_QA_POST_CIERRE_DISPARADO: ${acta.post_prohibidos.join(', ')}`;}});
  });
});
