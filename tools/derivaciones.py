"""Genera derivaciones MÁS A LA IZQUIERDA de FinLang a partir de su CFG en BNF pura.

Uso:  python tools/derivaciones.py            (imprime Markdown completo)
      python tools/derivaciones.py --compact  (agrupa cadenas de producciones unitarias con =>*)
      python tools/derivaciones.py --json     (salida estructurada)

La CFG de aquí es la misma del informe (sección de gramática; actualizada en el Hito 2).  Las alternativas EBNF de ANTLR
(*, ?, ( )) se expresan con no terminales auxiliares (stmtList, init, moneda, ...).
Terminal entre comillas = lexema fijo; MAYÚSCULAS = clase de token (ID, NUMERO, ...).
"""
import json, os, sys
from functools import lru_cache

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gen"))
from antlr4 import InputStream, CommonTokenStream
from FinLangLexer import FinLangLexer

# ----------------------------- gramática (BNF) -------------------------
G = {
 "program":      [["topList", "EOF"]],
 "topList":      [["topLevel", "topList"], []],
 "topLevel":     [["funcDecl"], ["statement"]],
 # funciones (Hito 2)
 "funcDecl":     [["'funcion'", "ID", "'('", "params", "')'", "':'", "tipo", "block"]],
 "params":       [["param", "paramTail"], []],
 "paramTail":    [["','", "param", "paramTail"], []],
 "param":        [["tipo", "ID"]],
 "returnStmt":   [["'retornar'", "expr", "';'"]],
 "stmtList":     [["statement", "stmtList"], []],
 "statement":    [["declaration"], ["assignment"], ["loanDecl"], ["printStmt"], ["ifStmt"],
                  ["whileStmt"], ["forStmt"], ["scheduleStmt"], ["returnStmt"], ["block"]],
 "block":        [["'{'", "stmtList", "'}'"]],
 # declaraciones
 "declaration":  [["tipo", "ID", "init", "';'"]],
 "init":         [["'='", "expr"], []],
 "tipo":         [["'num'"], ["'dinero'", "moneda"], ["'tasa'"], ["'bool'"]],
 "moneda":       [["'['", "CURRENCY", "']'"], []],
 # asignación
 "assignment":   [["ID", "'='", "expr", "';'"]],
 # préstamo y reportes
 "loanDecl":     [["'prestamo'", "ID", "'{'", "'monto'", "':'", "expr", "';'", "'tea'", "':'", "expr", "';'",
                   "'plazo'", "':'", "expr", "';'", "extras", "'}'"]],
 "extras":       [["extra", "extras"], []],
 "extra":        [["'comision'", "':'", "expr", "';'"], ["'seguro'", "':'", "expr", "';'"]],
 "printStmt":    [["'mostrar'", "expr", "exprTail", "';'"]],
 "exprTail":     [["','", "expr", "exprTail"], []],
 "scheduleStmt": [["'cronograma'", "ID", "';'"]],
 # selectivas e iterativas
 "ifStmt":       [["'si'", "'('", "expr", "')'", "statement", "elsePart"]],
 "elsePart":     [["'sino'", "statement"], []],
 "whileStmt":    [["'mientras'", "'('", "expr", "')'", "statement"]],
 "forStmt":      [["'para'", "ID", "'desde'", "expr", "'hasta'", "expr", "statement"]],
 # expresiones (estratificadas: la precedencia sale de los niveles)
 "expr":  [["expr", "'||'", "andE"], ["andE"]],
 "andE":  [["andE", "'&&'", "eqE"], ["eqE"]],
 "eqE":   [["eqE", "'=='", "relE"], ["eqE", "'!='", "relE"], ["relE"]],
 "relE":  [["relE", "'<'", "addE"], ["relE", "'<='", "addE"], ["relE", "'>'", "addE"],
           ["relE", "'>='", "addE"], ["addE"]],
 "addE":  [["addE", "'+'", "mulE"], ["addE", "'-'", "mulE"], ["mulE"]],
 "mulE":  [["mulE", "'*'", "unE"], ["mulE", "'/'", "unE"], ["unE"]],
 "unE":   [["'-'", "unE"], ["'!'", "unE"], ["prim"]],
 "prim":  [["'('", "expr", "')'"], ["NUMERO", "CURRENCY"], ["NUMERO"], ["PORCENTAJE"],
           ["'verdadero'"], ["'falso'"], ["STRING"], ["ID"],
           ["'cuota'", "'('", "ID", "')'"], ["'interesTotal'", "'('", "ID", "')'"],
           ["'convertir'", "'('", "expr", "','", "CURRENCY", "','", "expr", "')'"],
           ["'tcea'", "'('", "ID", "')'"], ["'tasaMensual'", "'('", "ID", "')'"],
           ["'capitalizar'", "'('", "expr", "','", "expr", "','", "expr", "')'"],
           ["ID", "'('", "args", "')'"]],
 "args":  [["expr", "argTail"], []],
 "argTail": [["','", "expr", "argTail"], []],
}
TOKEN_CLASSES = {"ID", "NUMERO", "PORCENTAJE", "STRING", "CURRENCY", "EOF"}

# ----------------------------- ejemplos ---------------------------------
EJEMPLOS = [
 ("Declaraciones", "declaration", [
   "num meses = 12;", "dinero saldo = 15000 PEN;", "dinero[USD] ahorro;", "bool meta = falso;"]),
 ("Asignaciones", "assignment", [
   "meses = meses + 1;", "tem = 2%;", "meta = verdadero;", "ahorro = 0 USD;"]),
 ("Expresiones", "expr", [
   "saldo * tem", "(a + b) / 2", "a > 1000 PEN && mes < 36", "convertir(saldo, USD, 3.75)"]),
 ("Sentencias selectivas", "ifStmt", [
   'si (meta) mostrar "ok";', "si (a == b) n = 1; sino n = 2;",
   'si (saldo > 0 PEN) { mostrar "ok"; }',
   "si (meta) n = 1; sino si (a > b) n = 2;"]),
 ("Sentencias iterativas", None, [
   ("whileStmt", "mientras (saldo > 0 PEN) saldo = saldo - cuota1;"),
   ("whileStmt", "mientras (!meta && mes < 36) mes = mes + 1;"),
   ("forStmt", "para i desde 1 hasta 12 saldo = saldo * tem;"),
   ("forStmt", "para k desde 1 hasta meses { n = n + 1; }")]),
 ("Préstamos y reportes", None, [
   ("loanDecl", "prestamo p { monto: 1000 PEN; tea: 10%; plazo: 12; }"),
   ("printStmt", 'mostrar "Cuota:", cuota(auto);'),
   ("scheduleStmt", "cronograma auto;"),
   ("printStmt", "mostrar interesTotal(auto);")]),
 ("Declaración de funciones (Hito 2)", "funcDecl", [
   "funcion doble(num n): num { retornar n * 2; }",
   "funcion r5(): tasa { retornar 1.5%; }",
   "funcion conIgv(dinero[PEN] m): dinero[PEN] { retornar m + m * 18%; }",
   "funcion suma(num a, num b): num { retornar a + b; }"]),
 ("Retornar (Hito 2)", "returnStmt", [
   "retornar x;", "retornar x * x + 1;", "retornar c > 1500 PEN;", "retornar convertir(c, PEN, 3.75);"]),
 ("Llamadas a funciones (Hito 2)", "expr", [
   "doble(meses)", "doble(meses) + 1", "margen(ingreso, 1200 PEN)", "r5()"]),
 ("Préstamo con costos (Hito 2)", "loanDecl", [
   "prestamo p1 { monto: 10000 PEN; tea: 20%; plazo: 12; comision: 10 PEN; }",
   "prestamo p2 { monto: 10000 PEN; tea: 20%; plazo: 12; seguro: 0.08%; }",
   "prestamo p3 { monto: 10000 PEN; tea: 20%; plazo: 12; comision: 10 PEN; seguro: 0.08%; }",
   "prestamo p4 { monto: 5000 USD; tea: 15%; plazo: 24; seguro: 0.05%; comision: 3 USD; }"]),
 ("Funciones del dominio (Hito 2)", "expr", [
   "tcea(p3)", "tasaMensual(auto)", "tcea(p3) > tasaMensual(p3)", "capitalizar(1000 PEN, 1%, 12)"]),
]

# ----------------------------- léxico -----------------------------------
def tokenize(text):
    lx = FinLangLexer(InputStream(text)); lx.removeErrorListeners()
    st = CommonTokenStream(lx); st.fill()
    names = FinLangLexer.symbolicNames
    return [(names[t.type], t.text) for t in st.tokens if t.type != -1]

def term_matches(sym, tok):
    cls, text = tok
    if sym.startswith("'"):
        return text == sym[1:-1]
    return cls == sym

# ----------------------------- parser por tramos ------------------------
def build_parser(toks):
    n = len(toks)
    @lru_cache(maxsize=None)
    def derive(A, i, j):
        for k, rhs in enumerate(G[A]):
            r = seq(A, k, 0, i, j)
            if r is not None:
                return (A, k, r)
        return None
    @lru_cache(maxsize=None)
    def seq(A, k, p, i, j):
        rhs = G[A][k]
        if p == len(rhs):
            return [] if i == j else None
        sym = rhs[p]
        rest_min = sum(1 for s in rhs[p+1:] if s in TOKEN_CLASSES or s.startswith("'"))
        if sym in G:
            for m in range(i, j + 1):
                if (A, i, j) == (A, i, m) and p == 0 and sym == A:   # recursión izquierda: tramo menor
                    if m == j: continue
                left = derive(sym, i, m)
                if left is None: continue
                tail = seq(A, k, p + 1, m, j)
                if tail is not None:
                    return [left] + tail
            return None
        if i < j and term_matches(sym, toks[i]):
            tail = seq(A, k, p + 1, i + 1, j)
            if tail is not None:
                return [("T", sym, toks[i][1])] + tail
        return None
    return derive

def parse(start, text):
    toks = tokenize(text)
    d = build_parser(tuple(toks))
    tree = d(start, 0, len(toks))
    if tree is None:
        raise ValueError(f"no derivable desde {start}: {text}")
    return tree

# ----------------------------- derivación -------------------------------
def leftmost(tree):
    """Devuelve [(forma, rhs_unitaria?)]; la primera forma es el símbolo inicial."""
    prefix, stack = [], [tree]
    def show():
        pend = []
        for node in reversed(stack):
            pend.append(node[1].strip("'") if node[0] == "T" else node[0])
        return " ".join(prefix + pend)
    steps = [(show(), False)]
    while stack:
        node = stack.pop()
        if node[0] == "T":
            prefix.append(node[2])
            continue
        A, k, kids = node
        rhs = G[A][k]
        unit = len(rhs) == 1 and rhs[0] in G
        stack.extend(reversed(kids))
        # consumir terminales que quedaron al tope: no cuentan como paso
        while stack and stack[-1][0] == "T":
            t = stack.pop(); prefix.append(t[2])
        steps.append((show() if (prefix or stack) else "ε", unit))
    return steps

def render(steps, compact):
    out, skipped = [steps[0][0]], False
    if not compact:
        return [steps[0][0]] + [s for s, _ in steps[1:]], [False] * (len(steps) - 1)
    arrows, i = [], 1
    while i < len(steps):
        form, unit = steps[i]
        skip = False
        while unit and i + 1 < len(steps):
            skip = True; i += 1; form, unit = steps[i]
        out.append(form); arrows.append(skip); i += 1
    return out, arrows

def all_derivations(compact=True):
    res = []
    for titulo, start, ejs in EJEMPLOS:
        items = []
        for e in ejs:
            s, txt = (start, e) if start else e
            steps = leftmost(parse(s, txt))
            forms, arrows = render(steps, compact)
            items.append({"start": s, "input": txt, "forms": forms, "star": arrows})
        res.append({"titulo": titulo, "items": items})
    return res

def to_text(item):
    lines = [f"{item['forms'][0]}"]
    for f, st in zip(item["forms"][1:], item["star"]):
        lines.append(f"  {'⇒*' if st else '⇒ '} {f}")
    return "\n".join(lines)

if __name__ == "__main__":
    compact = "--compact" in sys.argv
    data = all_derivations(compact)
    if "--json" in sys.argv:
        print(json.dumps(data, ensure_ascii=False, indent=1)); sys.exit()
    for g in data:
        print(f"\n## {g['titulo']}")
        for n, it in enumerate(g["items"], 1):
            print(f"\n**{n}.** `{it['input']}`  (desde `{it['start']}`)\n```\n{to_text(it)}\n```")
