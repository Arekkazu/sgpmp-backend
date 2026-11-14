import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {precioVigente,fechaApta,preInicial,sinCambios,evaluar,cierre8CoincideG32,CASOS,paresMatrizFaltantes,cuerpoParMatriz,numeroAislado} from '../lib/g43_core.mjs';
import {validarLecturas,contrato} from '../lib/contrato.mjs';
import {informe} from '../g43.mjs';
const dia='2026-11-09',base={id_precio_mercado:435,id_especie:422,categoria:'POR_CABEZA',id_metrica_produccion:null,fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-01',fecha_vencimiento:null};
const vencido={...base,id_precio_mercado:999,fecha_vigencia:'2026-11-02',fecha_vencimiento:'2026-11-08'};
assert.equal(precioVigente([base,vencido],422,'POR_CABEZA',dia),null);
assert.equal(precioVigente([base],422,'POR_CABEZA',dia)?.id_precio_mercado,435);
assert.equal(fechaApta(dia,[{id_periodo_contable:219,estado:'ABIERTO',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30'},{id_periodo_contable:220,estado:'ABIERTO',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30'}]),true);
const p={puede_cerrar:true,bloqueos:[],activos_sin_precio:[],lineas_sin_trazabilidad:[]};assert.equal(preInicial({...p,lineas_sin_trazabilidad:[{id_linea:17}]},p,p),true);assert.equal(preInicial(p,p,p),false);
const s={periodo:{estado:'ABIERTO'},lineas:[{id_linea_asiento_nic41:17,estado:'REGISTRADA',estado_trazabilidad:'VERIFICACION_PENDIENTE',id_periodo_contable:8}],comprobantes:[],variaciones:[]};assert.equal(sinCambios(s,s),true);assert.equal(sinCambios(s,{...s,lineas:[]}),false);
const conforme={pausaEstado:'EN_CIERRE',pIni:{id_precio_mercado:15,fecha_vigencia:'2026-11-01'},pNuevo:{id_precio_mercado:20},congelado:{id_precio_mercado:15,fecha_vigencia:'2026-11-01'},cierre8:{http:200},medicionesIni:true,aviso25:true,no25:true,si25:true,ui25:true,confirmacion26:true,costo26:true,sinEstimacion26:true,ui26:true,lista27:true,no27:true,si27:true,ui27:true};
const casos=evaluar(conforme);assert.deepEqual(Object.values(casos).map(x=>x.estado),CASOS.map(()=>'APROBADO'));
const actual=evaluar({...conforme,pausaEstado:'ABIERTO',cierre8:{http:500},confirmacion26:false,costo26:false,ui26:false,ui27:false});assert.deepEqual(Object.values(actual).map(x=>x.estado),['RECHAZADO','APROBADO','RECHAZADO','RECHAZADO']);
assert.equal(cierre8CoincideG32({http:500},[{tipo_evento:'CIERRE_PERIODO_FALLIDO',timestamp_evento:'2026-11-09T21:24:36Z',payload_evento:{paso:3,error:'Error interno'}}],'2026-11-09T21:24:20Z'),true);
assert.equal(cierre8CoincideG32({http:500},[],'2026-11-09T21:24:20Z'),false);
const textoInforme=informe({run_id:'RUN-G43-V1-LOCAL',version:1,autorizacion_referencia:'LOCAL',casos:{},precios:[],activos:[],lineas:[],cypress:{paneles:{}},incidencias:[{id:'INC-LOCAL',casos:[],esperado:'autorización',obtenido:'decisión',evidencia:'resultado.json',impacto:'valoración',severidad:'MEDIA',justificacion_severidad:'Impacto parcial comprobado.',certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'API',hipotesis:'por determinar',accion:'revisar'}],herramientas:{node:process.version},evidencias:[],problemas_tecnicos:[],rollback:{verificado:false},oficial:false});
const patronCodificacion=/\u00C3|\uFFFD|(?<=\p{L})\?(?=\p{L})/u;
assert.ok(!patronCodificacion.test(textoInforme));
assert.ok(patronCodificacion.test('confirmaci'+'?'+'n'));
const raiz=path.resolve(import.meta.dirname,'..');
function archivosFuente(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(entrada=>{
  const ruta=path.join(dir,entrada.name);
  if(entrada.isDirectory())return archivosFuente(ruta);
  return /\.(?:mjs|js|cjs|json)$/.test(entrada.name)||entrada.name==='README.md'?[ruta]:[];
});}
for(const ruta of archivosFuente(raiz)){
  const fuente=fs.readFileSync(ruta,'utf8');
  assert.ok(!fuente.startsWith('\uFEFF'),`${path.relative(raiz,ruta)} tiene BOM`);
  const textos=ruta.endsWith('README.md')?[fuente]:[...fuente.matchAll(/"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'|`(?:\\[\s\S]|[^`\\])*`/g)].map(x=>x[0]);
  for(const literal of textos){
    const sinConsultas=literal.replace(/\?[A-Za-z_][A-Za-z_0-9]*=/g,'=');
    // El extractor simple también captura código entre comillas de expresiones regulares.
    const errorReal=/\u00C3|\uFFFD/u.test(sinConsultas)||(!sinConsultas.includes(';')&&/(?<=\p{L})\?(?=\p{L})/u.test(sinConsultas));
    assert.ok(!errorReal,`${path.relative(raiz,ruta)} contiene texto mal codificado`);
  }
}
assert.ok(textoInforme.includes('Severidad MEDIA: Impacto parcial comprobado.'));
const schema=contrato.rutas.find(x=>x.metodo==='GET'&&x.ruta==='/finanzas/periodos/{id}/prevalidacion');assert.ok(schema.respuesta.activos_sin_precio[0].especie);
const fixture={bloqueos:[],activos_sin_precio:[{id_activo_biologico:1568,identificador:'A',especie:'Caprino',campo_inyectado:'X'}],lineas_sin_trazabilidad:[],puede_cerrar:true,requiere_autorizacion:true,campo_inyectado:'X'};
const inyectado=validarLecturas(fixture,'GET','/finanzas/periodos/219/prevalidacion',{estricto:false});assert.equal(inyectado.activos_sin_precio[0].especie,'Caprino');
assert.throws(()=>validarLecturas(fixture,'GET','/finanzas/periodos/219/prevalidacion',{estricto:true}).campo_inyectado,/LECTURA_FUERA_CONTRATO/);
const roto={...fixture,activos_sin_precio:[{id_activo_biologico:1568,identificador:'A'}]};assert.throws(()=>validarLecturas(roto,'GET','/finanzas/periodos/219/prevalidacion',{estricto:true}).activos_sin_precio[0].especie,/CAMPO_AUSENTE/);
assert.equal(numeroAislado('10 activos',1),false);assert.equal(numeroAislado('1 activo',1),true);
const matriz=[{tipo_hecho:'OTRO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'},{tipo_hecho:'OTRO',sentido:'GANANCIA',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'},{tipo_hecho:'OTRO',sentido:'PERDIDA',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'}];
assert.equal(paresMatrizFaltantes(matriz).length,4);assert.equal(cuerpoParMatriz(matriz,['DEPRECIACION_ACTIVO_COSTO','UNICO']).sentido,'UNICO');assert.equal(cuerpoParMatriz([],['DEPRECIACION_ACTIVO_COSTO','UNICO']),null);
const calc=contrato.rutas.find(x=>x.metodo==='GET'&&x.ruta==='/finanzas/periodos/{id}/calculos').respuesta[0];assert.ok(!Object.hasOwn(calc,'id_precio_mercado'));assert.equal(calc.precio_unitario,'decimal');
const calculo={id_calculo_valor_razonable:1,id_activo_biologico:945,tiene_valor_estimado:false,fecha_calculo:dia+'T12:00:00Z',precio_unitario:'9300',magnitud:'1',valor_razonable_bruto:'9300',valor_neto:'9000'};
assert.throws(()=>validarLecturas([calculo],'GET','/finanzas/periodos/8/calculos',{estricto:true})[0].id_precio_mercado,/LECTURA_FUERA_CONTRATO/);
assert.equal(validarLecturas([calculo],'GET','/finanzas/periodos/8/calculos',{estricto:true})[0].precio_unitario,'9300');
const cong=contrato.rutas.find(x=>x.metodo==='GET'&&x.ruta==='/finanzas/periodos').respuesta[0].ultimo_cierre.precios_congelados[0];assert.equal(cong.id_precio_mercado,'integer');
console.log('OK g43_local: decisiones, contrato y campos inyectados');
