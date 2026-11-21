# Servidor simulado SOLO para probar la colección (no el producto). Replica la lógica leída en
# consultar_historial_predictivo_use_case.py y el router (fase 1), incluido el límite de 731 días.
# | 2026-11-20 | v3: activo de baja 2946, otra finca 2556, linea base completa y escenarios de control |
import json, sys, uuid
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

TOK_VET, TOK_PROD = "eyJ" + "mockvet", "eyJ" + "mockprod"
SECRETO = "secreto-sandbox-de-prueba-123456"

def hoy():
    return (datetime.now(timezone.utc) - timedelta(hours=5)).date()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def out(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("X-Request-Id", str(uuid.uuid4())); self.end_headers(); self.wfile.write(data)
    def err(self, code, ec, msg="x"):
        self.out(code, {"error_code": ec, "message": msg, "fields": [], "timestamp": "t"})
    def check(self):
        if self.headers.get("X-Sandbox-Secret") != SECRETO or not self.headers.get("X-Test-Run-Id"):
            self.err(403, "SANDBOX"); return False
        if self.headers.get("X-Zona-Horaria") != "America/Bogota":
            self.err(400, "SIN_ZONA"); return False
        return True
    def do_POST(self):
        if not self.check(): return
        n = int(self.headers.get("Content-Length", 0)); b = json.loads(self.rfile.read(n))
        tok = TOK_VET if b["correo_electronico"].startswith("vet") else TOK_PROD
        self.out(200, {"token": tok, "tipo": "Bearer", "expira_en": 3600, "message": "ok"})
    def do_DELETE(self):
        if not self.check(): return
        self.out(200, {"status": "Rollback exitoso"})
    def do_GET(self):
        if not self.check(): return
        u = urlparse(self.path); q = parse_qs(u.query); auth = self.headers.get("Authorization", "")
        if u.path == "/usuarios/me":
            return self.out(200, {"id_usuario": 97, "nombre_rol": "Veterinario", "correo_electronico": "vet@x.co"})
        if u.path == "/prediccion/auditoria":
            return self.out(200, {"total": 12, "pagina": 1, "por_pagina": 1, "items": [{"id_evento": "aaaa-1"}]})
        if u.path == "/reportes/opciones/finca":
            return self.out(200, [{"valor": 84, "etiqueta": "Finca A"}, {"valor": 184, "etiqueta": "Finca B"}])
        if u.path == "/activos-biologicos/885":
            return self.out(200, {"id_activo_biologico": 885, "identificador": "QA-1", "nombre_estado": "ACTIVO", "id_finca": 184, "id_especie": 220, "tipo": "INDIVIDUAL"})
        if u.path == "/activos-biologicos/885/eventos":
            return self.out(200, {"id_activo_biologico": 885, "total": 2, "eventos": [{"id_eventos": 10, "fecha": "2026-10-25T05:06:22+00:00", "sanitario": {"tipo": "DIAGNOSTICO"}}, {"id_eventos": 11, "fecha": "2026-10-24T00:00:00+00:00"}]})
        if u.path == "/prediccion/retroalimentacion/bandeja":
            return self.out(200, {"items": [{"id_resultado_inferencia": "32985675-aaaa", "numero_evaluaciones": 1}], "total": 1, "pagina": 1})
        if u.path == "/prediccion/historial/885":
            return self.out(200, {"eventos": [{"tipo_evento": "INFERENCIA"}, {"tipo_evento": "RETROALIMENTACION"}], "cursor_siguiente": None, "total_pagina": 2})
        if u.path == "/activos-biologicos":
            if auth == "Bearer " + TOK_PROD:
                return self.out(200, {"total_registros": 2, "pagina_actual": 1, "total_paginas": 1, "registros_por_pagina": 100, "registros": [{"id_activo_biologico": 776, "nombre_estado": "ACTIVO", "id_finca": 57}, {"id_activo_biologico": 778, "nombre_estado": "ACTIVO", "id_finca": 184}]})
            f = int(q["id_finca"][0])
            regs = [{"id_activo_biologico": 885, "nombre_estado": "ACTIVO", "id_finca": f}] + ([{"id_activo_biologico": 555, "nombre_estado": "BAJA", "id_finca": f}, {"id_activo_biologico": 930, "nombre_estado": "BAJA", "id_finca": f}] if f == 184 else [])
            return self.out(200, {"total_registros": len(regs), "pagina_actual": 1, "total_paginas": 1, "registros_por_pagina": 100, "registros": regs})
        if not u.path.startswith("/historial-predictivo/"): return self.err(404, "RUTA")
        if auth != "Bearer " + TOK_VET: return self.err(403, "PERMISO_DENEGADO")
        raw = u.path.rsplit("/", 1)[1]
        try: ida = int(raw)
        except ValueError: return self.err(400, "VAL_ENTRADA")
        niv = [int(x) for x in q.get("nivel_riesgo", [])]
        if any(x not in (0, 1, 2, 3) for x in niv): return self.err(400, "VAL_ENTRADA")
        fin = date.fromisoformat(q["fecha_fin"][0]) if "fecha_fin" in q else hoy()
        ini = date.fromisoformat(q["fecha_inicio"][0]) if "fecha_inicio" in q else fin - timedelta(days=365)
        if ini > fin: return self.err(400, "VAL_ENTRADA")
        if (fin - ini).days > 731: return self.err(400, "VAL_ENTRADA")
        if ida not in (885, 777, 555, 2556, 2946): return self.err(404, "ACTIVO_INEXISTENTE")
        if ida in (777, 2556): return self.err(403, "FINCA_NO_AUTORIZADA")
        if ida == 555 or (ida == 2946 and MODO != "baja_200"):
            return self.err(422, "ACTIVO_NO_VIGENTE", "El historial predictivo solo se muestra para animales activos o en tratamiento.")
        global CONT
        if ida == 885 and not u.query:
            CONT += 1
        preds = [
            {"tipo": "PREDICCION", "fecha": "2026-10-20T22:06:22+00:00", "id_resultado_inferencia": "p1", "nivel_riesgo": 3},
            {"tipo": "PREDICCION", "fecha": "2026-10-21T12:00:00+00:00", "id_resultado_inferencia": "p2", "nivel_riesgo": 3},
            {"tipo": "PREDICCION", "fecha": "2026-10-22T12:00:00+00:00", "id_resultado_inferencia": "p3", "nivel_riesgo": 2},
            {"tipo": "PREDICCION", "fecha": "2026-10-23T23:06:22+00:00", "id_resultado_inferencia": "p4", "nivel_riesgo": 2},
            {"tipo": "PREDICCION", "fecha": "2026-10-24T19:06:22+00:00", "id_resultado_inferencia": "p5", "nivel_riesgo": 1},
            {"tipo": "PREDICCION", "fecha": "2026-10-26T21:06:22+00:00", "id_resultado_inferencia": "p6", "nivel_riesgo": 0},
            {"tipo": "PREDICCION", "fecha": "2026-10-28T00:06:22+00:00", "id_resultado_inferencia": "p7", "nivel_riesgo": 3},
        ]
        evs = [] if MODO == "vacio" else [
            {"tipo": "EVENTO_SANITARIO", "id_evento": 2684, "fecha": "2026-10-25T05:06:22+00:00"},
            {"tipo": "EVENTO_SANITARIO", "id_evento": 2685, "fecha": "2026-10-26T21:36:22+00:00"},
            {"tipo": "EVENTO_SANITARIO", "id_evento": 2686, "fecha": "2026-10-28T20:06:22+00:00"},
        ]
        fr = "2026-11-20T15:08:00+00:00"
        rets = [] if MODO in ("vacio", "sin_valoraciones") else [
            {"fecha": fr, "id_resultado_inferencia": "p1", "valoracion": "CORRECTO"},
            {"fecha": fr, "id_resultado_inferencia": "p2", "valoracion": "INCORRECTO"},
            {"fecha": fr, "id_resultado_inferencia": "p3", "valoracion": "PARCIAL"},
            {"fecha": fr, "id_resultado_inferencia": "p4", "valoracion": "SIN_EVENTO"},
        ]
        if MODO == "cambia" and CONT >= 3:
            rets.append({"fecha": fr, "id_resultado_inferencia": "p5", "valoracion": "CORRECTO"})
        return self.out(200, {
            "activo": {"id_activo_biologico": 885, "estado": "ACTIVO"},
            "rango_fechas_aplicado": {"fecha_inicio": ini.isoformat(), "fecha_fin": fin.isoformat()},
            "ventana_correspondencia_horas": 12,
            "predicciones": preds,
            "eventos_sanitarios": evs,
            "retroalimentaciones": rets,
            "grupos": [], "correspondencias": [],
            "tvco": {"porcentaje": 25.0, "texto": "25%", "tvco_denominador": 4, "tvco_excluidas_conflicto": 0,
                     "excluidas_sin_retroalimentacion": 3, "tasa_error": 75.0},
            "pendientes": {"total": 3, "pagina": 1, "por_pagina": 20, "items": []},
            "metadatos": {"total_inferencias": 7, "total_eventos_sanitarios": 3, "total_retroalimentaciones": 4,
                          "total_pendientes": 3, "total_conflictos": 0},
            "fuentes_no_disponibles": [], "mensaje": None, "modo_visualizacion": "LINEAL"})

MODO = sys.argv[2] if len(sys.argv) > 2 else "completo"
CONT = 0
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
