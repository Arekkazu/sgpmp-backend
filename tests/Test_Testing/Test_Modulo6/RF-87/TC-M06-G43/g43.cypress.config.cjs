// Base de TC-M06-G40/g40.cypress.config.cjs; adaptada a los paneles de G43.
const fs=require('node:fs'),path=require('node:path');
const dir=process.env.CYPRESS_ARTIFACTS_DIR;
module.exports={fixturesFolder:false,video:false,screenshotOnRunFailure:false,trashAssetsBeforeRuns:false,reporter:'spec',screenshotsFolder:dir?path.join(dir,'screenshots'):path.join(__dirname,'cypress-no-ejecutar'),e2e:{specPattern:'g43.cy.js',supportFile:false,testIsolation:true,setupNodeEvents(on){on('after:run',r=>{if(dir){fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'G43-cypress.json'),JSON.stringify({totalTests:r.totalTests,totalPassed:r.totalPassed,totalFailed:r.totalFailed,specs:r.runs?.length??0},null,2));}});}}};
