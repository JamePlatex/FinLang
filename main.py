"""Driver de FinLang.

Uso:
    python main.py archivo.fin             # análisis completo
    python main.py archivo.fin --tokens    # muestra tokens (analizador léxico)
    python main.py archivo.fin --tree      # muestra árbol sintáctico
    python main.py archivo.fin --ir        # imprime el LLVM IR generado
    python main.py archivo.fin --ir salida.ll   # guarda el LLVM IR en un archivo
    python main.py archivo.fin --run       # genera LLVM IR y lo ejecuta (JIT)
    python main.py archivo.fin --obj salida.o   # código objeto nativo (enlazar con: cc salida.o -lm)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen"))

from antlr4 import InputStream, CommonTokenStream
from antlr4.error.ErrorListener import ErrorListener

from FinLangLexer import FinLangLexer
from FinLangParser import FinLangParser
from semantic import SemanticAnalyzer


class Collector(ErrorListener):
    def __init__(self, tag, sink):
        super().__init__()
        self.tag, self.sink = tag, sink

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.sink.append(f"[{self.tag}] Línea {line}:{column + 1} - {msg}")


def analyze(text, show_tokens=False, show_tree=False, ctx=None):
    """Devuelve (errores_lexicos, errores_sintacticos, errores_semanticos).
    Si se pasa un dict en ctx, deja ahí el árbol y el analizador semántico."""
    lex_errors, syn_errors = [], []

    lexer = FinLangLexer(InputStream(text))
    lexer.removeErrorListeners()
    lexer.addErrorListener(Collector("LEX", lex_errors))
    stream = CommonTokenStream(lexer)
    stream.fill()

    # Los caracteres no reconocidos llegan como ERROR_CHAR
    for t in stream.tokens:
        if t.type == FinLangLexer.ERROR_CHAR:
            lex_errors.append(f"[LEX] Línea {t.line}:{t.column + 1} - carácter no reconocido '{t.text}'")

    if show_tokens:
        names = FinLangLexer.symbolicNames
        for t in stream.tokens:
            if t.type != -1:
                print(f"{names[t.type]:<14} {t.text!r:<20} ({t.line}:{t.column + 1})")

    if lex_errors:                    # no tiene sentido parsear con tokens inválidos
        return lex_errors, syn_errors, []

    parser = FinLangParser(stream)
    parser.removeErrorListeners()
    parser.addErrorListener(Collector("SIN", syn_errors))
    tree = parser.program()

    if show_tree:
        print(tree.toStringTree(recog=parser))

    sem_errors = []
    if not lex_errors and not syn_errors:
        sa = SemanticAnalyzer()
        sa.visit(tree)
        # Orden por posición (la pasada previa de funciones puede reportar antes)
        sem_errors = sorted(sa.errors, key=lambda e: tuple(map(int, e.split("Línea ")[1].split(" ")[0].split(":"))))
        if ctx is not None:
            ctx.update(tree=tree, sema=sa)
    return lex_errors, syn_errors, sem_errors


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    args = sys.argv[2:]
    ctx = {}
    lex, syn, sem = analyze(text, "--tokens" in args, "--tree" in args, ctx)
    errors = lex + syn + sem
    for e in errors:
        print(e)
    if errors:
        print(f"\n{len(errors)} error(es) encontrado(s).")
        return 1
    backend = {"--ir", "--run", "--obj"} & set(args)
    if not backend:
        print("OK: análisis léxico, sintáctico y semántico sin errores.")
        return 0

    from codegen import CodeGen, run_jit, emit_object
    module = CodeGen(ctx["sema"], name=os.path.basename(sys.argv[1])).generate(ctx["tree"])

    def arg_after(flag):
        i = args.index(flag)
        return args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith("--") else None

    if "--ir" in args:
        out = arg_after("--ir")
        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(str(module))
            print(f"LLVM IR guardado en {out}")
        else:
            print(module)
    if "--obj" in args:
        out = arg_after("--obj") or "salida.o"
        emit_object(module, out)
        print(f"Código objeto guardado en {out} (enlazar con: cc {out} -lm -o programa)")
    if "--run" in args:
        sys.stdout.flush()
        return run_jit(module)
    return 0


if __name__ == "__main__":
    sys.exit(main())
