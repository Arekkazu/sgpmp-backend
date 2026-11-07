"""Verificaciones de SOLO LECTURA del flujo bovino en DEV (Potrero 1). Solo hace GET."""
import json, sys, datetime as dt, urllib.request, urllib.parse
B="https://api.inmero.co/api-sgpmp-dev"; TOK=open(sys.argv[1]).read().strip(); OUT=sys.argv[2]
def get(path, **q):
    q={k:v for k,v in q.items() if v is not None}
    url=B+path+("?"+urllib.parse.urlencode(q) if q else "")
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+TOK})
    return json.load(urllib.request.urlopen(req,timeout=40))
def pag(path, listkey="items", **q):
    out=[];p=1
    while True:
        d=get(path,pagina=p,por_pagina=100,**q); out+=d[listkey]
        if p>=d.get("paginas_totales",1) or not d[listkey]: break
        p+=1
    return out
R=[]  # (id, verificacion, resultado, detalle)
def chk(i,desc,ok,det=""): R.append((i,desc,"PASA" if ok else ("INFO" if ok is None else "FALLA"),det))
hoy=dt.date.today().isoformat()
# umbrales DEV del bovino (id_especie=2)
um=get("/configuracion/umbrales",id_especie=2); um=um.get("items",um)
bandas={}   # id_variable -> dict
for u in um:
    niv=sorted([(float(n["limite_inferior"]),float(n["limite_superior"]),n["nivel"]) for n in u["niveles"]])
    cont=all(niv[i][1]==niv[i+1][0] for i in range(len(niv)-1)) and niv[0][0]==float(u["valor_min"]) and niv[-1][1]==float(u["valor_max"])
    bandas[u["id_variable_ambiental"]]=dict(niv=niv,min=float(u["valor_min"]),max=float(u["valor_max"]),id=u.get("id_umbral_ambiental"))
    chk("U1",f"Umbral var {u['id_variable_ambiental']}: 3 niveles contiguos que cubren [{u['valor_min']},{u['valor_max']}]",cont and len(niv)==3,str([(a,b,n) for a,b,n in niv]))
    chk("U2",f"Umbral var {u['id_variable_ambiental']}: sincronizado con el Edge",u.get("estado_sincronizacion")=="APLICADA",str(u.get("estado_sincronizacion")))
def banda(idv,v):
    b=bandas[idv]
    if v<b["min"] or v>b["max"]: return "fuera"
    hits=[n for a,c,n in b["niv"] if a<=v<=c]
    return hits[0] if len(hits)==1 else "frontera:"+"/".join(hits)
SEM={"normal":"VERDE","precaucion":"AMARILLO","critico":"ROJO"}
# V1 dispositivo
est=get("/iot/dispositivos/5/estado")["estado"]
chk("D1","PC-BOV-001 en estado ACTIVO",est["estado_actual"]=="ACTIVO",est["estado_actual"])
chk("D2","Ultimo contacto hace menos de 5 min",est["tiempo_sin_contacto"] is not None and est["tiempo_sin_contacto"]<300,f"{est['tiempo_sin_contacto']} s")
# V2/V3 telemetria de hoy
total={}
for sid,nom in ((6,"FC-BOV"),(7,"TEMP-CORP-BOV")):
    its=pag("/iot/monitoreo/historial",fecha_inicio=hoy,fecha_fin=hoy,sensor_id=sid,orden="asc")
    total[nom]=its
    ts=[i["timestamp_captura"] for i in its]
    chk("T1",f"{nom}: hay lecturas hoy",len(its)>0,f"{len(its)} lecturas")
    chk("T2",f"{nom}: sin timestamps duplicados",len(set(ts))==len(ts),f"{len(ts)-len(set(ts))} duplicados")
    chk("T3",f"{nom}: orden cronologico ascendente",ts==sorted(ts))
    mal=[i for i in its if i["estado_calidad"]!="LECTURA_VALIDA"]
    raras=[i["id_telemetria"] for i in mal if i["estado_calidad"]!="ERROR_CALIBRACION"]
    chk("T4",f"{nom}: ninguna lectura con estado distinto de LECTURA_VALIDA / ERROR_CALIBRACION",not raras,f"raras: {raras[:10]}")
    if mal: chk("T4b",f"{nom}: lecturas ERROR_CALIBRACION",None,f"{len(mal)} de {len(its)}: ids {[i['id_telemetria'] for i in mal]}, capturas {[i['timestamp_captura'][11:19] for i in mal]}, valor_ajustado={ {i['valor_ajustado'] for i in mal} }")
    chk("T5",f"{nom}: origen_dato TIEMPO_REAL",all(i["origen_dato"]=="TIEMPO_REAL" for i in its),str({i['origen_dato'] for i in its}))
    chk("T6",f"{nom}: valor_ajustado == valor en las LECTURA_VALIDA (sin calibracion)",all(i["valor"]==i["valor_ajustado"] for i in its if i["estado_calidad"]=="LECTURA_VALIDA"),"")
    chk("T7",f"{nom}: ligadas a umbral e individuo",all(i["id_umbral_ambiental"] and i["id_activo_biologico"] for i in its),f"activo={ {i['identificador_activo'] for i in its} }")
    # intervalos
    dts=[dt.datetime.fromisoformat(t.replace("Z","+00:00")) for t in ts]
    gaps=[(dts[k+1]-dts[k]).total_seconds() for k in range(len(dts)-1)]
    if gaps:
        mx=max(gaps); chk("T8",f"{nom}: sin huecos mayores a 10 min",mx<=600,f"intervalo max {mx:.0f} s, mediana {sorted(gaps)[len(gaps)//2]:.0f} s")
    # semaforo historico vs banda DEV
    idv=its[0]["id_variable"] if its else None
    mism=[];front=[]
    for i in its:
        v=float(i["valor"]); bd=banda(idv,v)
        if bd.startswith("frontera"): front.append((i["id_telemetria"],v,bd))
        elif bd=="fuera": 
            if i["estado_semaforo_historico"]!="ROJO": mism.append((i["id_telemetria"],v,"fuera",i["estado_semaforo_historico"]))
        elif SEM[bd]!=i["estado_semaforo_historico"]: mism.append((i["id_telemetria"],v,bd,i["estado_semaforo_historico"]))
    chk("S1",f"{nom}: semaforo historico coincide con la banda del umbral DEV",not mism,f"{len(mism)} discrepancias de {len(its)}: {mism[:6]}")
    if front: chk("S2",f"{nom}: lecturas exactamente en una frontera (inclusividad)",None,f"{front[:5]}")
    # estadisticas
    est_=get("/iot/monitoreo/historial",fecha_inicio=hoy,fecha_fin=hoy,sensor_id=sid,por_pagina=1)["estadisticas"][0]
    vals=[float(i["valor"]) for i in its]; b=bandas[idv]
    fuera_rango=100*sum(1 for v in vals if v<b["min"] or v>b["max"])/len(vals)
    fuera_normal=100*sum(1 for v in vals if banda(idv,v)!="normal")/len(vals)
    chk("E1",f"{nom}: total_lecturas de estadisticas = lecturas devueltas",est_["total_lecturas"]==len(its),f"{est_['total_lecturas']} vs {len(its)}")
    chk("E2",f"{nom}: minimo/maximo de estadisticas",abs(float(est_["valor_minimo"])-min(vals))<1e-6 and abs(float(est_["valor_maximo"])-max(vals))<1e-6,f"api {est_['valor_minimo']}-{est_['valor_maximo']} vs calc {min(vals)}-{max(vals)}")
    chk("E3",f"{nom}: pct_fuera_rango",None,f"api {est_['pct_fuera_rango']} % | calculado fuera de [min,max]={fuera_rango:.2f} % | fuera de banda normal={fuera_normal:.2f} %")
# V5 alertas
al=pag("/iot/alertas",id_infraestructura=2)
chk("A1","Alertas de Potrero 1 consultables",len(al)>0,f"{len(al)} alertas")
validos={"ACTIVA","EN_ATENCION","RESUELTA","DESCARTADA","VENCIDA"}
chk("A2","estado_alerta dentro del catalogo RF-57",all(a["estado_alerta"] in validos for a in al),str({a['estado_alerta'] for a in al}))
chk("A3","severidad dentro de LEVE/MODERADO/CRITICO",all(a["severidad"] in {"LEVE","MODERADO","CRITICO"} for a in al),str({a['severidad'] for a in al}))
tab={}
for a in al:
    if a.get("metadato_evento") and a["metadato_evento"].get("nivel_umbral"):
        tab.setdefault((a["metadato_evento"]["nivel_umbral"],a["severidad"]),0); tab[(a["metadato_evento"]["nivel_umbral"],a["severidad"])]+=1
chk("A4","Relacion nivel_umbral -> severidad observada",None,str(tab))
crit=[a for a in al if a.get("metadato_evento") and a["metadato_evento"].get("nivel_umbral")=="critico"]
chk("A5","Toda alerta de nivel critico tiene severidad CRITICO",all(a["severidad"]=="CRITICO" for a in crit),f"{len(crit)} alertas criticas")
# valor de la alerta cae en la banda que dice el nivel
nm={"TEMPERATURA CORPORAL":13,"TEMP_CORPORAL":13,"FRECUENCIA CARDIACA":14,"FRECUENCIA_CARDIACA":14,"Frecuencia Cardiaca":14,"Temperatura Corporal":13}
incoh=[]
for a in al:
    md=a.get("metadato_evento") or {}; idv=nm.get(a["tipo_variable"])
    if idv and md.get("nivel_umbral") and a.get("valor") is not None:
        bd=banda(idv,float(a["valor"]))
        if bd!=md["nivel_umbral"] and not bd.startswith("frontera"): incoh.append((a["id_alerta"],a["valor"],md["nivel_umbral"],bd))
chk("A6","El valor de cada alerta cae en la banda DEV de su nivel_umbral",not incoh,f"{len(incoh)} incoherentes: {incoh[:6]}")
# cobertura: lecturas en banda critica/precaucion y alerta cercana
cob=[];antes=[]
vers=max(dt.datetime.fromisoformat(i["version_umbral"].replace("Z","+00:00")) for k in total for i in total[k])
for nom,idv in (("TEMP-CORP-BOV",13),("FC-BOV",14)):
    for i in total[nom]:
        bd=banda(idv,float(i["valor"]))
        if bd in("critico",):
            t0=dt.datetime.fromisoformat(i["timestamp_captura"].replace("Z","+00:00"))
            cerca=[a for a in al if abs((dt.datetime.fromisoformat(a["fecha_evento"].replace("Z","+00:00"))-t0).total_seconds())<=180]
            if not cerca: (antes if t0<vers else cob).append((nom,i["id_telemetria"],i["valor"],i["timestamp_captura"]))
chk("A7","Toda lectura en banda critica POSTERIOR a la ultima version del umbral tiene una alerta a +-3 min",not cob,f"version umbral {vers.isoformat()}; sin alerta: {cob[:6]}")
if antes: chk("A7b","Lecturas en banda critica ANTERIORES a la version del umbral sin alerta",None,f"{len(antes)}: {antes}")
vv={(k,i["version_umbral"]) for k in total for i in total[k]}
chk("V1","version_umbral que muestra el historial: una sola por sensor aunque la lectura sea anterior a esa version",None,f"{sorted(vv)} (el historial parece mostrar el umbral VIGENTE, no el vigente al capturar; no verificado)")
# V7 dashboard
dsh=get("/iot/monitoreo/dashboard/2")
for s in dsh["sensores"]:
    idv={"Frecuencia Cardiaca":14,"Temperatura Corporal":13}.get(s["tipo_variable"])
    if idv:
        bd=banda(idv,float(s["ultimo_valor"]))
        chk("M1",f"Dashboard {s['nombre_sensor']}: semaforo actual coincide con la banda",SEM.get(bd)==s["estado_semaforo"],f"valor {s['ultimo_valor']} banda {bd} semaforo {s['estado_semaforo']}")
    else:
        chk("M2",f"Dashboard {s['nombre_sensor']} ({s['tipo_variable']}): semaforo",None,f"valor {s['ultimo_valor']} {s['ultima_unidad']} -> {s['estado_semaforo']} (sin_umbral={s.get('sin_umbral')})")
u=dsh["resumen_unidades"][0]
chk("M3","Estado general de la unidad vs peor semaforo de sus sensores",None,f"estado_general={u['estado_general']}; sensores={[ (s['nombre_sensor'],s['estado_semaforo']) for s in dsh['sensores']]}; sensores_online={u['sensores_online']}/{u['total_sensores']}")
json.dump(R,open(OUT,"w"),ensure_ascii=False,indent=1)
n={k:sum(1 for r in R if r[2]==k) for k in("PASA","FALLA","INFO")}
print(n)
for r in R:
    if r[2]!="PASA": print(r[2],r[0],r[1],"::",r[3][:300])
