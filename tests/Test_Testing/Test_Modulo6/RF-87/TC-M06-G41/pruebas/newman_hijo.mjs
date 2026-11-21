import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
export async function ejecutar(input){
  const dir=path.resolve(input.salida);if(path.basename(dir)!=='newman'||!dir.includes(`${path.sep}RUN-G41-V`))throw Error('SALIDA_FUERA_RUN');
  fs.mkdirSync(dir,{recursive:true});const json=path.join(dir,'newman-G41.json'),html=path.join(dir,'newman-G41.html');
  const newman=require(path.join(path.dirname(process.execPath),'node_modules','newman'));
  const {error,summary}=await new Promise(resolve=>newman.run({collection:input.coleccion,environment:input.environment,
    reporters:['json','htmlextra'],reporter:{json:{export:json},htmlextra:{export:html,skipSensitiveData:true}},
    silent:true,timeoutRequest:120000,timeout:300000,ignoreRedirects:true},(error,summary)=>resolve({error,summary})));
  const secrets=input.environment.values.filter(x=>/token|secret|password|email/i.test(x.key)).map(x=>String(x.value)).filter(x=>x.length>3);
  for(const file of [json,html])if(fs.existsSync(file)){let content=fs.readFileSync(file,'utf8');if(file===json){const clean=(v,k='')=>/^(stream|body|headers|header|cookies|auth|authorization|raw)$/i.test(k)?'[REDACTADO]':Array.isArray(v)?v.map(x=>clean(x)):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([key,x])=>[key,clean(x,key)])):v;content=JSON.stringify(clean(JSON.parse(content)),null,2);}for(const s of secrets)content=content.split(s).join('[REDACTADO]');content=content.replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g,'[JWT_REDACTADO]').replace(/[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[CORREO_REDACTADO]');fs.writeFileSync(file,content);}
  return{codigo:error?2:0,fallos:summary?.run?.failures?.length??-1,solicitudes:summary?.run?.executions?.length??0,reportes:[json,html].every(x=>fs.existsSync(x))};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const r=await ejecutar(JSON.parse(fs.readFileSync(0,'utf8')));process.stdout.write(JSON.stringify(r));if(r.codigo||r.fallos||!r.reportes)process.exitCode=2;}
  catch(e){process.stdout.write(JSON.stringify({codigo:2,error:e.code??e.message}));process.exitCode=2;}
}
