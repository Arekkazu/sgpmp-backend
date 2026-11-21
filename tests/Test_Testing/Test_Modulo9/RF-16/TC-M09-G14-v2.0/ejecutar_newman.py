"""Ejecutor directo de Newman para TC-M09-G14-v2.0."""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parents[4]
ENV_TEST = REPO_DIR / ".env.test"

if ENV_TEST.exists():
    load_dotenv(ENV_TEST)
else:
    load_dotenv()

admin_pwd = os.getenv("TEST_ADMIN_PASSWORD")
if not admin_pwd:
    print("ERROR: TEST_ADMIN_PASSWORD no encontrada", file=sys.stderr)
    sys.exit(1)

html_out = BASE_DIR / "resultados" / "resultado_TC-M09-G14-v2.0.html"
consola_out = BASE_DIR / "evidencias" / "consola_TC-M09-G14-v2.0.txt"
collection_file = BASE_DIR / "tc-m09-g14-v2.0.postman_collection.json"

cmd = [
    "cmd.exe", "/c", "newman", "run", str(collection_file),
    "--env-var", f"admin_password={admin_pwd}",
    "-r", "htmlextra,cli",
    "--reporter-htmlextra-export", str(html_out),
    "--reporter-htmlextra-skipSensitiveData",
    "--reporter-htmlextra-skipEnvironmentVars",
    "--reporter-htmlextra-skipGlobalVars"
]

print(f"Ejecutando Newman en {BASE_DIR}...")
with open(consola_out, "w", encoding="utf-8") as f_out:
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), stdout=f_out, stderr=subprocess.STDOUT)

print(f"Newman finalizó con código {proc.returncode}")

# Extraer y guardar evidencias/nombres_corrida.json si fue emitido
try:
    import json
    import re
    if consola_out.exists():
        content = consola_out.read_text(encoding="utf-8", errors="ignore")
        m_nombres = re.search(r"NOMBRES_CORRIDA_JSON=(\{.*?\})", content)
        if m_nombres:
            nombres_data = json.loads(m_nombres.group(1))
            nombres_file = BASE_DIR / "evidencias" / "nombres_corrida.json"
            nombres_file.parent.mkdir(parents=True, exist_ok=True)
            with open(nombres_file, "w", encoding="utf-8") as f_n:
                json.dump(nombres_data, f_n, indent=2, ensure_ascii=False)
            print(f"Evidencia generada: {nombres_file}")
except Exception as e:
    print(f"Aviso al extraer nombres_corrida: {e}", file=sys.stderr)

sys.exit(proc.returncode)
