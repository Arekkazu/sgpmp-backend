import {escenario} from './fixture_g40.mjs';
for(const [name,options] of [['conforme',{alerta:true}],['sin_alerta',{alerta:false}],
  ['cypress_fallido',{cypressFail:true}],['matriz_no_restaurada',{matrizNoRestaurada:true}]]){
  const x=await escenario(name,options);const r=x.resultado;
  console.log(`OK escenario_${name}: 018=${r.casos['TC-M06-018'].estado} oficial=${r.oficial?'sí':'no'} solicitudes=${x.requests}/150`);
  if(x.overlaps||x.requests>150)process.exitCode=2;
}
