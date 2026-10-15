// Real TEST only. Intercepts observe network traffic; no responses are replaced.
Cypress.Screenshot.defaults({blackout:['input[type="password"]','input[type="email"]'],capture:'viewport'});
describe('G23 - rechazo visual de rangos invalidos',()=>{
 it(Cypress.env('caso'),()=>{
  let token:string,plan:any;
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
   cy.task('discover',{token},{log:false}).then(p=>{plan=p;});
  });
  cy.location('pathname').should('not.include','login');
  // Navigate through the real SPA menu; a hard reload would require refresh.
  cy.contains('nav.ds-sidebar button',/^Configuración$/).should('have.attr','aria-disabled','false').click();
  cy.location('pathname').should('eq','/configuracion');
  cy.contains('button',/^Por especie$/i).click();
  cy.then(()=>cy.contains('button',plan.especie).click());
  cy.intercept('GET','**/configuracion/umbrales?*').as('umbrales');
  cy.contains('button','Umbrales Ambientales').click();
  cy.wait('@umbrales',{log:false}).its('response.statusCode').should('eq',200);
  cy.contains('button','Nuevo umbral').scrollIntoView().should('be.visible').click({scrollBehavior:'center'});
  cy.get('[role="dialog"]').should('be.visible');
  cy.intercept('POST','**/configuracion/umbrales',req=>{
   req.continue(res=>{posts.push({status:res.statusCode,payload:req.body,response:res.body});});
  }).as('create');
  cy.then(()=>{
   const p=plan.payload;
   cy.get('select[name="id_variable_ambiental"]').select(String(p.id_variable_ambiental));
   cy.get('input[name="valor_min"]').clear().type(String(p.valor_min));
   cy.get('input[name="valor_max"]').clear().type(String(p.valor_max));
   // For an invalid parent range, level defaults are irrelevant: the client
   // prevents submit on min/max before a request can be issued. Avoid the
   // unrelated TEST layout overlap between level inputs.
  });
  cy.get('[role="dialog"]').screenshot(`${Cypress.env('caso')}-datos-invalidos`);
  cy.contains('button','Registrar umbral').click();
  cy.get('[role="dialog"]').should('be.visible').and('contain.text','Debe ser mayor al mínimo.').and('contain.text','Debe ser menor al máximo.');
  cy.get('[role="dialog"]').screenshot(`${Cypress.env('caso')}-validacion`);
  cy.then(()=>{
   cy.request({method:'GET',url:`${Cypress.env('api')}/configuracion/umbrales?id_especie=${plan.payload.id_especie}`,headers:{Authorization:`Bearer ${token}`},log:false,failOnStatusCode:false,retryOnNetworkFailure:false}).then(r=>{
    const persisted=Array.isArray(r.body.items)?r.body.items.filter(u=>u.id_variable_ambiental===plan.payload.id_variable_ambiental):null;
    cy.task('evidence',{plan,posts,postGetStatus:r.status,persisted,messages:['Debe ser menor al máximo.','Debe ser mayor al mínimo.'],STOP_ALL:!!persisted?.length||posts.some(p=>p.status===201)},{log:false});
    expect(r.status,'GET posterior').eq(200);
    expect(persisted,'combinacion sin persistencia').to.have.length(0);
    for(const p of posts){expect(p.status,'POST si se envia').eq(400);expect(p.response.error_code).eq('VAL_ENTRADA');}
   });
  });
  cy.get('@create.all',{log:false}).then((requests:any)=>{
   expect(requests.length,'UI bloquea POST por validacion local').eq(0);
  });
 });
});
