"""Pruebas numéricas: compara lo que calcula el código LLVM generado con el oráculo
independiente (tools/oraculo.py, basado en numpy-financial). Tolerancia: 0.01 en montos (se imprimen con 2 decimales) y 0.0005 puntos porcentuales en tasas."""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import oraculo

CASOS = [  # (monto, moneda, tea %, plazo, comision, seguro %)
    (30000, "USD", 12, 36, 0, 0),
    (10000, "PEN", 20, 12, 10, 0.08),
    (8000, "PEN", 24.5, 18, 0, 0),
    (150000, "PEN", 9.5, 240, 15, 0.03),
    (2500, "EUR", 45, 6, 5, 0),
    (1000, "PEN", 100, 1, 0, 0),
]


def compilar(m, cur, tea, n, com, seg):
    src = (f"prestamo p {{ monto: {m} {cur}; tea: {tea}%; plazo: {n}; comision: {com} {cur}; seguro: {seg}%; }}\n"
           f"mostrar cuota(p), interesTotal(p), tasaMensual(p), tcea(p);\ncronograma p;\n")
    with tempfile.NamedTemporaryFile("w", suffix=".fin", delete=False, encoding="utf-8") as f:
        f.write(src)
    out = subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), f.name, "--run"],
                         capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
    os.unlink(f.name)
    return out


ok = fail = 0
for caso in CASOS:
    m, cur, tea, n, com, seg = caso
    out = compilar(*caso)
    head = out[0].split()               # "cuota CUR interes CUR tem% tcea%"
    got = {"cuota": float(head[0]), "interés": float(head[2]),
           "TEM %": float(head[4].rstrip('%')), "TCEA %": float(head[5].rstrip('%'))}
    exp = {"cuota": oraculo.cuota(m, tea / 100, n), "interés": oraculo.interes_total(m, tea / 100, n),
           "TEM %": oraculo.tem(tea / 100) * 100, "TCEA %": oraculo.tcea(m, tea / 100, n, com, seg / 100) * 100}
    errores = [f"{k}: {got[k]} vs {exp[k]:.4f}" for k in got if abs(got[k] - exp[k]) > (0.01 if "%" not in k else 0.0005)]
    filas = [l.split() for l in out if l.strip() and l.split()[0].isdigit()]
    ref = oraculo.cronograma(m, tea / 100, n, com, seg / 100)
    if len(filas) != n:
        errores.append(f"cronograma con {len(filas)} filas, se esperaban {n}")
    for f, r in zip(filas, ref):
        dif = max(abs(float(a) - b) for a, b in zip(f[1:], r[1:]))
        if dif > 0.011:
            errores.append(f"fila {f[0]}: diferencia {dif:.4f}")
            break
    good = not errores
    ok += good; fail += not good
    print("PASS" if good else "FAIL", "num.  ", f"préstamo {m} {cur}, TEA {tea}%, {n} meses, comisión {com}, seguro {seg}%",
          f"(cuota, interés, TEM, TCEA y {n} filas del cronograma vs numpy-financial)" if good else errores)
print(f"{ok} OK, {fail} FAIL")
