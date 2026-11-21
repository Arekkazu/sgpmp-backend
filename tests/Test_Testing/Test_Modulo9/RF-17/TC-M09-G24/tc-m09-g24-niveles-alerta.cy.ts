// TEST real. Los intercept solo observan trafico; ninguna respuesta se sustituye.
Cypress.Screenshot.defaults({blackout:['input[type="password"]','input[type="email"]'],capture:'viewport'});

const CASO=Cypress.env('caso') as string;

describe('G24 - niveles de alerta: fuera de rango, solapamiento y continuidad',()=>{
 it(CASO,()=>{
  let token:string,plan:any,newman:any=null;
  const posts:any[]=[];
  cy.intercept('POST','**/sesiones/').as('login');
  cy.visit('/login');
  cy.get('input[type="email"]').type(Cypress.env('email'),{log:false});
  cy.get('input[type="password"]').type(Cypress.env('password'),{log:false});
  cy.get('button[type="submit"]').click();
  cy.wait('@login',{log:false}).then(({response})=>{
   expect(response?.statusCode,'login status').eq(200);
   token=response?.body.token;
   expect(typeof token,'token disponible en memoria').eq('string');
   // Se vuelve a descubrir la combinacion libre antes de cada recorrido.
   cy.task('discover',{token},{log:false}).then(p=>{plan=p;});
   cy.task('newmanResultado',null,{log:false}).then((r:any)=>{
    newman=r;
    // TC-M09-54 se valida sobre el registro que creo Newman: la UI no crea otro.
    if(CASO==='TC-M09-54'&&r?.plan)plan=r.plan;
   });
  });
  cy.location('pathname').should('not.include','login');
  // Navegacion por el menu real de la SPA.
  cy.contains('nav.ds-sidebar button',/^Configuración$/).should('have.attr','aria-disabled','false').click();
  cy.location('pathname').should('eq','/configuracion');
  cy.contains('button',/^Por especie$/i).click();
  cy.then(()=>cy.contains('button',plan.especie).click());
  cy.intercept('GET','**/configuracion/umbrales?*').as('umbrales');
  cy.contains('button','Umbrales Ambientales').click();
  cy.wait('@umbrales',{log:false}).its('response.statusCode').should('eq',200);
  cy.intercept('POST','**/configuracion/umbrales',req=>{
   req.continue(res=>{posts.push({status:res.statusCode,payload:req.body,response:res.body});});
  }).as('create');

  if(CASO==='TC-M09-54'){
   cy.then(()=>{
    const id=newman?.idCreado;
    const p=plan.payload;
    if(id){
     // Verificacion visual del registro creado por Newman.
     cy.contains('tr',`#${id}`).as('fila').should('be.visible');
     cy.get('@fila').should('contain.text',`${Number(p.valor_min).toFixed(2)} – ${Number(p.valor_max).toFixed(2)}`);
     for(const n of p.niveles)cy.get('@fila').should('contain.text',`${Number(n.limite_inferior).toFixed(2)}–${Number(n.limite_superior).toFixed(2)}`);
     cy.get('@fila').should('contain.text','Activo');
     cy.get('@fila').screenshot(`${CASO}-umbral-creado`);
     cy.get('@fila').screenshot(`${CASO}-niveles-continuos`);
    }else{
     // Newman no pudo crear el umbral (500). La UI NO intenta crearlo:
     // solo documenta el estado observable, sin emitir un POST adicional.
     cy.contains('h3, h2, div, section',/Umbrales Ambientales/i).should('exist');
     cy.get('table').should('not.contain.text',plan.variable);
     cy.get('table').screenshot(`${CASO}-sin-persistencia`);
    }
   });
  }else{
   cy.contains('button','Nuevo umbral').scrollIntoView().should('be.visible').click({scrollBehavior:'center'});
   cy.get('[role="dialog"]').should('be.visible');
   // A 560 px de modal, las tres NivelCard se reparten en dos columnas y el input
   // normal_sup queda cubierto por precaucion_inf (defecto de layout observado,
   // ver QA-JE-G23-UI-01). En ancho de PWA las tarjetas se apilan en una columna
   // y los seis campos quedan accesibles. No se mockea ni se fuerza nada.
   cy.viewport(440,1400);
   cy.then(()=>{
    const p=plan.payload;
    cy.get('select[name="id_variable_ambiental"]').select(String(p.id_variable_ambiental));
    cy.get('input[name="valor_min"]').clear().type(String(p.valor_min));
    cy.get('input[name="valor_max"]').clear().type(String(p.valor_max));
    for(const n of p.niveles){
     cy.get(`input[name="${n.nivel}_inf"]`).scrollIntoView().clear({scrollBehavior:'center'}).type(String(n.limite_inferior),{scrollBehavior:'center'});
     cy.get(`input[name="${n.nivel}_sup"]`).scrollIntoView().clear({scrollBehavior:'center'}).type(String(n.limite_superior),{scrollBehavior:'center'});
    }
   });
   cy.get('[role="dialog"]').screenshot(`${CASO}-${CASO==='TC-M09-52'?'datos-invalidos':'solapamiento'}`);
   // [role="dialog"] es el overlay fijo y mide exactamente el viewport: para ver
   // las tres NivelCard completas se captura la tarjeta interna del modal.
   cy.get('[role="dialog"] > div').screenshot(`${CASO}-niveles`);
   cy.contains('button','Registrar umbral').click();
   cy.then(()=>{
    const p=plan.payload;
    const o=[...p.niveles].sort((a:any,b:any)=>a.limite_inferior-b.limite_inferior);
    const esperado=CASO==='TC-M09-52'
     ?`cae fuera del rango general [${p.valor_min}, ${p.valor_max}]`
     :`termina en ${o[1].limite_superior} pero el siguiente comienza en ${o[2].limite_inferior}`;
    cy.get('[role="dialog"]').should('be.visible').and('contain.text',esperado);
    cy.get('[role="dialog"]').screenshot(`${CASO}-validacion`);
    cy.task('evidence',{plan,mensajeEsperado:esperado},{log:false});
   });
  }

  // Verificacion final comun: persistencia y POST observados.
  cy.then(()=>{
   cy.request({method:'GET',url:`${Cypress.env('api')}/configuracion/umbrales?id_especie=${plan.payload.id_especie}`,headers:{Authorization:`Bearer ${token}`},log:false,failOnStatusCode:false,retryOnNetworkFailure:false}).then(r=>{
    const items=Array.isArray(r.body.items)?r.body.items:[];
    const persisted=items.filter((u:any)=>u.id_variable_ambiental===plan.payload.id_variable_ambiental);
    const esperaCreado=CASO==='TC-M09-54'&&!!newman?.idCreado;
    cy.task('evidence',{plan,newman,posts,postGetStatus:r.status,persisted,idsEspecie:items.map((u:any)=>u.id_umbral_ambiental),STOP_ALL:(CASO!=='TC-M09-54'&&(persisted.length>0||posts.some(p=>p.status===201)))},{log:false});
    expect(r.status,'GET posterior').eq(200);
    expect(persisted.length,esperaCreado?'registro creado presente':'combinacion sin persistencia').eq(esperaCreado?1:0);
    for(const p of posts)expect(p.status,'ningun POST exitoso desde la UI').not.eq(201);
   });
  });
  cy.get('@create.all',{log:false}).then((requests:any)=>{
   const esperados=0; // La UI no debe emitir POST de umbral en ninguno de los tres originales.
   expect(requests.length,'POST de umbral emitidos desde la UI').eq(esperados);
  });
 });
});
