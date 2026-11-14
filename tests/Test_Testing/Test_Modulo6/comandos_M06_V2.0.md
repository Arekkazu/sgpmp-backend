# Comandos de la corrida V2.0 — Módulo 6 (reprueba del 12-nov-2026)

Todos los reportes salen como `reporte-TC-M06-GXX-V2.0.html` dentro de la carpeta de cada grupo (no pisan los anteriores). Ejecutar desde la raíz de `sgpmp-backend`, en PowerShell.

## 1. Variables de entorno (una vez por ventana de PowerShell)

```powershell
$env:TEST_SANDBOX_SECRET = "<secreto del sandbox>"
$env:QA_CONTRASENA_ADMIN = "<contraseña de admin@pecuaria.co>"
$env:QA_CONTRASENA_INGENIERO = "<contraseña de ingedecampo6@gmail.com>"
# Solo para G05, G07, G08, G22 y G30:
$env:QA_CONTRASENA_PRODUCTOR = "<contraseña de daniiella.vargass@gmail.com>"
$env:QA_CONTRASENA_VETERINARIO = "<contraseña de mariajosecastillovargas57@gmail.com>"
```

Los grupos pueden correr en varias ventanas a la vez (máximo 5 corridas simultáneas del sandbox).

## 2. Grupos G01 a G30 (pytest)

### RF-82

**TC-M06-G01**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G01/TC-M06-G01.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G01/reporte-TC-M06-G01-V2.0.html" --self-contained-html
```

**TC-M06-G02**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G02/TC-M06-G02.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G02/reporte-TC-M06-G02-V2.0.html" --self-contained-html
```

**TC-M06-G03**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G03/TC-M06-G03.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G03/reporte-TC-M06-G03-V2.0.html" --self-contained-html
```

**TC-M06-G04**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G04/TC-M06-G04.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G04/reporte-TC-M06-G04-V2.0.html" --self-contained-html
```

**TC-M06-G05** — 021 puede fallar otra vez si ningún campo muestra PENDIENTE_CONFIRMACION (decisión pendiente del líder); 022 Administrador (INC-304).

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G05/TC-M06-G05.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G05/reporte-TC-M06-G05-V2.0.html" --self-contained-html  # necesita productor y veterinario
```

**TC-M06-G06**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G06/TC-M06-G06.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G06/reporte-TC-M06-G06-V2.0.html" --self-contained-html
```

**TC-M06-G07**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G07/TC-M06-G07.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G07/reporte-TC-M06-G07-V2.0.html" --self-contained-html  # necesita productor y veterinario
```

**TC-M06-G08**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G08/TC-M06-G08.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-82/TC-M06-G08/reporte-TC-M06-G08-V2.0.html" --self-contained-html  # necesita productor y veterinario
```

### RF-83

**TC-M06-G09**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G09/TC-M06-G09.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G09/reporte-TC-M06-G09-V2.0.html" --self-contained-html
```

**TC-M06-G10**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G10/TC-M06-G10.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G10/reporte-TC-M06-G10-V2.0.html" --self-contained-html
```

**TC-M06-G11**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G11/TC-M06-G11.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G11/reporte-TC-M06-G11-V2.0.html" --self-contained-html
```

**TC-M06-G12**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G12/TC-M06-G12.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G12/reporte-TC-M06-G12-V2.0.html" --self-contained-html
```

**TC-M06-G13**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G13/TC-M06-G13.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G13/reporte-TC-M06-G13-V2.0.html" --self-contained-html
```

**TC-M06-G14**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G14/TC-M06-G14.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G14/reporte-TC-M06-G14-V2.0.html" --self-contained-html
```

**TC-M06-G15** — 072b y 072a: ahora deben pasar con el PR #1024 desplegado (filtros id_evento y tiene_valor_estimado).

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G15/TC-M06-G15.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-83/TC-M06-G15/reporte-TC-M06-G15-V2.0.html" --self-contained-html
```

### RF-84

**TC-M06-G16** — 078 ya no exige tipo_costo como campo (RFC-024 C24.3).

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G16/TC-M06-G16.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G16/reporte-TC-M06-G16-V2.0.html" --self-contained-html
```

**TC-M06-G17**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G17/TC-M06-G17.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G17/reporte-TC-M06-G17-V2.0.html" --self-contained-html
```

**TC-M06-G18**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G18/TC-M06-G18.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G18/reporte-TC-M06-G18-V2.0.html" --self-contained-html
```

**TC-M06-G19**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G19/TC-M06-G19.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G19/reporte-TC-M06-G19-V2.0.html" --self-contained-html
```

**TC-M06-G20**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G20/TC-M06-G20.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G20/reporte-TC-M06-G20-V2.0.html" --self-contained-html
```

**TC-M06-G21**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G21/TC-M06-G21.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G21/reporte-TC-M06-G21-V2.0.html" --self-contained-html
```

**TC-M06-G22**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G22/TC-M06-G22.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-84/TC-M06-G22/reporte-TC-M06-G22-V2.0.html" --self-contained-html  # necesita productor y veterinario
```

### RF-85

**TC-M06-G23**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G23/TC-M06-G23.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G23/reporte-TC-M06-G23-V2.0.html" --self-contained-html
```

**TC-M06-G24**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G24/TC-M06-G24.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G24/reporte-TC-M06-G24-V2.0.html" --self-contained-html
```

**TC-M06-G25**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G25/TC-M06-G25.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G25/reporte-TC-M06-G25-V2.0.html" --self-contained-html
```

**TC-M06-G26**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G26/TC-M06-G26.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G26/reporte-TC-M06-G26-V2.0.html" --self-contained-html
```

**TC-M06-G27** — 122 (g, lb, arroba, t) debe pasar con la conversión desplegada y exige el texto «Cantidad convertida».

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G27/TC-M06-G27.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G27/reporte-TC-M06-G27-V2.0.html" --self-contained-html
```

**TC-M06-G28**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G28/TC-M06-G28.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G28/reporte-TC-M06-G28-V2.0.html" --self-contained-html
```

**TC-M06-G29**

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G29/TC-M06-G29.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G29/reporte-TC-M06-G29-V2.0.html" --self-contained-html
```

**TC-M06-G30** — El caso 137 (precio manual por rol) se repite en Newman aparte; aquí corre el pytest.

```powershell
python -m pytest "tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G30/TC-M06-G30.py" -v -s -rs --noconftest --html="tests/Test_Testing/Test_Modulo6/RF-85/TC-M06-G30/reporte-TC-M06-G30-V2.0.html" --self-contained-html  # necesita productor y veterinario
```

## 3. G31 (Cypress, repo del front)

Desde `SGPMP-FRONT-END-PWA/testing/test_testing/Modulo6/RF-82/TC-M06-G31`. Genera `RESULTADOS/resultado_TC-M06-G31-V2.0.html`.

```powershell
$env:CYPRESS_TEST_SANDBOX_SECRET = "<secreto del sandbox>"
$env:CYPRESS_QA_CONTRASENA_ADMIN = "<contraseña de admin@pecuaria.co>"
$env:CYPRESS_QA_CONTRASENA_INGENIERO = "<contraseña de ingedecampo6@gmail.com>"
$env:CYPRESS_QA_CONTRASENA_PRODUCTOR = "<contraseña de daniiella.vargass@gmail.com>"
$env:CYPRESS_QA_CONTRASENA_VETERINARIO = "<contraseña de mariajosecastillovargas57@gmail.com>"
npx cypress run --browser chrome
```
