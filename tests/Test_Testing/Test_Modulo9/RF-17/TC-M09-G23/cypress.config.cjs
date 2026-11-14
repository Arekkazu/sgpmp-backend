const {defineConfig}=require('cypress');
const path=require('path'),fs=require('fs');
const {FRONT,BASE,settings,discover,save,clean}=require('./helpers.cjs');
const {caso,id}=settings();
const screenshots=path.join(__dirname,'RESULTADOS','screenshots',id);
if(fs.existsSync(screenshots)||fs.existsSync(path.join(__dirname,'RESULTADOS',`cypress-${caso}-${id}.json`)))throw Error('G23_RUN_ID ya utilizado por Cypress');
module.exports=defineConfig({
 video:false,screenshotOnRunFailure:true,trashAssetsBeforeRuns:false,
 screenshotsFolder:screenshots,viewportWidth:1920,viewportHeight:1200,
 retries:0,defaultCommandTimeout:15000,requestTimeout:25000,responseTimeout:30000,
 env:{caso,runId:id,api:BASE,email:process.env.TEST_ADMIN_EMAIL,password:process.env.TEST_ADMIN_PASSWORD},
 e2e:{baseUrl:FRONT,specPattern:'tc-m09-g23-rangos-invalidos.cy.ts',supportFile:false,
  setupNodeEvents(on){
   on('task',{
    async discover({token}){return discover(token,caso);},
    evidence(data){save(`ui-${caso}-${id}.json`,{caso,...data});return null;}
   });
   on('after:run',results=>save(`cypress-${caso}-${id}.json`,{
    caso,status:results.totalFailed===0&&results.totalPassed===1?'PASS':'FAIL',
    tests:results.totalTests,passed:results.totalPassed,failed:results.totalFailed,
    browser:results.browserName,browserVersion:results.browserVersion,cypressVersion:results.cypressVersion,
    runs:results.runs?.map(r=>({spec:r.spec.name,screenshots:r.screenshots.map(s=>({path:path.relative(__dirname,s.path),testFailure:s.testFailure})),tests:r.tests.map(t=>({title:t.title,state:t.state,errors:[t.displayError,...t.attempts.map(a=>a.error?.message)].filter(Boolean).map(clean)}))}))
   }));
  }
 }
});
