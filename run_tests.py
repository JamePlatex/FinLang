"""Ejecuta todas las pruebas de FinLang.

1. Front end: cada tests/*.fin declara en su primera línea el resultado esperado
   (// ESPERA: OK | LEX | SIN | E01..E17 | EJE). Se comparan los códigos obtenidos.
2. Back end: todo programa válido se compila a LLVM IR y se ejecuta (JIT).
   Si el archivo tiene líneas '// SALIDA: ...', la salida debe coincidir exactamente.
   '// ESPERA: EJE' indica un error que solo puede detectarse en ejecución.
3. Numéricas: tests/numericos.py compara cronogramas y TCEA con un oráculo
   independiente (numpy-financial).

Uso: python run_tests.py [--solo-frontend]
"""
import glob, os, re, subprocess, sys
from main import analyze

HERE = os.path.dirname(os.path.abspath(__file__))


def run_program(path):
    r = subprocess.run([sys.executable, os.path.join(HERE, "main.py"), path, "--run"],
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    return r.returncode, r.stdout.splitlines(), r.stderr


ok = fail = 0
backend = "--solo-frontend" not in sys.argv
for path in sorted(glob.glob(os.path.join(HERE, "tests", "*.fin"))):
    name = os.path.relpath(path, HERE)
    text = open(path, encoding="utf-8").read()
    esperado = set(re.search(r"ESPERA:\s*(.*)", text).group(1).split())
    esperado.discard("OK")
    if not backend and "EJE" in esperado:
        continue                                  # requiere ejecutar el programa
    salida = re.findall(r"^// SALIDA: ?(.*)$", text, re.M)
    lex, syn, sem = analyze(text)
    obtenido = {re.match(r"\[(\w+)\]", e).group(1) for e in lex + syn + sem}
    detalle = ""
    if backend and not obtenido:
        code, out, err = run_program(path)
        if any(l.startswith("[EJE]") for l in out):
            obtenido.add("EJE")
        elif code != 0:
            obtenido.add("CRASH")
            detalle = err.strip().splitlines()[-1] if err.strip() else f"exit {code}"
        if salida and "EJE" not in esperado and out != salida:
            detalle = f"salida distinta:\n      esperada {salida}\n      obtenida {out}"
    good = obtenido == esperado and not detalle
    ok += good; fail += not good
    tipo = "ejec." if (backend and not esperado) or "EJE" in esperado else "      "
    print(("PASS" if good else "FAIL"), tipo, name, "esperado:", sorted(esperado) or ["OK"],
          "obtenido:", sorted(obtenido) or ["OK"], (f"({len(salida)} líneas de salida)" if salida and good else ""))
    if detalle:
        print("     ", detalle)

if backend:
    r = subprocess.run([sys.executable, os.path.join(HERE, "tests", "numericos.py")], capture_output=True, text=True)
    print(r.stdout.rstrip())
    m = re.search(r"(\d+) OK, (\d+) FAIL", r.stdout)
    if m:
        ok += int(m.group(1)); fail += int(m.group(2))
    else:
        fail += 1; print(r.stderr)
print(f"\n{ok} OK, {fail} FAIL")
sys.exit(1 if fail else 0)
