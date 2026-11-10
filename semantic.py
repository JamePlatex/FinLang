"""Analizador semántico de FinLang (visitor sobre el árbol de ANTLR4).

Errores semánticos verificados:
  E01  Variable/préstamo no declarado
  E02  Identificador ya declarado en el mismo ámbito
  E03  Tipos incompatibles (declaración, asignación, campos de préstamo, etc.)
  E04  Operación entre monedas distintas (ej. PEN + USD)
  E05  Operación no válida para los tipos dados (ej. dinero + num)
  E06  Tasa fuera de rango (debe estar en (0%, 100%])
  E07  Monto o plazo inválido en préstamo (<= 0, o plazo no entero)
  E08  Condición que no es booleana (si / mientras)
  E09  Identificador no es un préstamo (o préstamo usado como valor)
  E10  Variable 'dinero' sin moneda (sin [MONEDA] ni valor inicial)
Agregados en el Hito 2 (funciones y costos del préstamo):
  E11  Llamada a una función no declarada (o a algo que no es función)
  E12  Número de argumentos incorrecto
  E13  Tipo de argumento incorrecto
  E14  'retornar' con un tipo distinto al declarado por la función
  E15  'retornar' fuera de una función
  E16  La función no retorna en todos los caminos
  E17  Comisión o seguro inválido (negativo, o seguro >= 100%)
Regla general: toda mezcla de monedas distintas se reporta como E04.
"""
from FinLangParser import FinLangParser
from FinLangVisitor import FinLangVisitor


class Ty:
    def __init__(self, kind, cur=None):
        self.kind = kind          # num, tasa, bool, texto, dinero, prestamo, error
        self.cur = cur            # moneda (para dinero / prestamo)

    def __eq__(self, o):
        return isinstance(o, Ty) and self.kind == o.kind and self.cur == o.cur

    def __hash__(self):
        return hash((self.kind, self.cur))

    def __str__(self):
        if self.kind == 'dinero' and self.cur:
            return f"dinero[{self.cur}]"
        return self.kind

    @property
    def bad(self):
        return self.kind == 'error'


NUM, TASA, BOOL, TEXTO, ERR = Ty('num'), Ty('tasa'), Ty('bool'), Ty('texto'), Ty('error')


def money(cur):
    return Ty('dinero', cur)


class SemanticAnalyzer(FinLangVisitor):
    def __init__(self):
        self.scopes = [{}]
        self.errors = []
        self.funcs = {}        # nombre -> (lista de (nombre, Ty) de parámetros, Ty de retorno)
        self.current_func = None
        self._analizadas = set()
        self.types = {}        # nodo expr -> Ty (lo usa el generador de código)

    def visit(self, tree):
        r = super().visit(tree)
        if isinstance(tree, FinLangParser.ExprContext):
            self.types[tree] = r
        return r

    # ----------------------------- utilidades -------------------------
    def err(self, node, code, msg):
        tok = node.start if hasattr(node, 'start') else node.symbol
        self.errors.append(f"[{code}] Línea {tok.line}:{tok.column + 1} - {msg}")

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def declare(self, id_node, ty):
        name = id_node.getText()
        if name in self.scopes[-1] or (self.scopes[-1] is self.scopes[0] and name in self.funcs):
            self.err(id_node, 'E02', f"'{name}' ya fue declarado en este ámbito")
        else:
            self.scopes[-1][name] = ty

    def resolve_tipo(self, t):
        if t.TNUM():
            return NUM
        if t.TTASA():
            return TASA
        if t.TBOOL():
            return BOOL
        return money(t.CURRENCY().getText() if t.CURRENCY() else None)

    def const_value(self, e):
        """Valor numérico de un literal (admite signo '-' y paréntesis); None si no es constante."""
        if isinstance(e, (FinLangParser.MoneyLitContext, FinLangParser.NumLitContext)):
            return float(e.NUMERO().getText())
        if isinstance(e, FinLangParser.RateLitContext):
            return float(e.PORCENTAJE().getText()[:-1])
        if isinstance(e, FinLangParser.ParensContext):
            return self.const_value(e.expr())
        if isinstance(e, FinLangParser.UnaryContext) and e.op.text == '-':
            v = self.const_value(e.expr())
            return -v if v is not None else None
        return None

    @staticmethod
    def _mixed_currency(a, b):
        return a.kind == 'dinero' and b.kind == 'dinero' and a.cur and b.cur and a.cur != b.cur

    def loan_of(self, id_node):
        name = id_node.getText()
        ty = self.lookup(name)
        if ty is None:
            self.err(id_node, 'E01', f"'{name}' no ha sido declarado")
            return None
        if ty.kind != 'prestamo':
            self.err(id_node, 'E09', f"'{name}' no es un préstamo")
            return None
        return ty

    # ----------------------------- sentencias -------------------------
    def visitProgram(self, ctx):
        # Pasada previa: firmas de todas las funciones (permite llamar antes de definir y recursión)
        for top in ctx.topLevel():
            f = top.funcDecl()
            if f is None:
                continue
            name = f.ID().getText()
            params = []
            for p in (f.paramList().param() if f.paramList() else []):
                pty = self.resolve_tipo(p.tipo())
                if pty.kind == 'dinero' and pty.cur is None:
                    self.err(p.ID(), 'E10', f"el parámetro '{p.ID().getText()}' es 'dinero' pero no tiene moneda (use dinero[PEN])")
                    pty = ERR
                params.append((p.ID().getText(), pty))
            ret = self.resolve_tipo(f.tipo())
            if ret.kind == 'dinero' and ret.cur is None:
                self.err(f.tipo(), 'E10', f"la función '{name}' retorna 'dinero' sin moneda (use dinero[PEN])")
                ret = ERR
            if name in self.funcs:
                self.err(f.ID(), 'E02', f"la función '{name}' ya fue declarada")
                continue
            self.funcs[name] = (params, ret)
        for top in ctx.topLevel():
            self.visit(top)
        return None

    def visitTopLevel(self, ctx):
        return self.visit(ctx.getChild(0))

    @classmethod
    def _returns(cls, st):
        """True si la sentencia retorna en todos sus caminos."""
        if st.returnStmt():
            return True
        if st.block():
            return any(cls._returns(x) for x in st.block().statement())
        if st.ifStmt():
            br = st.ifStmt().statement()
            return len(br) == 2 and cls._returns(br[0]) and cls._returns(br[1])
        return False

    def visitFuncDecl(self, ctx):
        name = ctx.ID().getText()
        sig = self.funcs.get(name)
        if sig is None or name in self._analizadas:
            return None                                   # duplicada: ya se reportó E02
        self._analizadas.add(name)
        params, ret = sig
        saved, self.scopes = self.scopes, [self.scopes[0], {}]
        for p, (pname, pty) in zip(ctx.paramList().param() if ctx.paramList() else [], params):
            self.declare(p.ID(), pty)
        self.current_func = (name, ret)
        body = ctx.block().statement()
        for st in body:                                    # el cuerpo comparte ámbito con los parámetros
            self.visit(st)
        if not any(self._returns(st) for st in body):
            self.err(ctx.ID(), 'E16', f"la función '{name}' no retorna un valor en todos los caminos")
        self.current_func = None
        self.scopes = saved
        return None

    def visitReturnStmt(self, ctx):
        ety = self.visit(ctx.expr())
        if self.current_func is None:
            self.err(ctx, 'E15', "'retornar' solo puede usarse dentro de una función")
            return
        name, ret = self.current_func
        if ety.bad or ret.bad:
            return
        if self._mixed_currency(ret, ety):
            self.err(ctx.expr(), 'E04', f"la función '{name}' retorna {ret} pero se retorna {ety}; use convertir()")
        elif ety != ret:
            self.err(ctx.expr(), 'E14', f"la función '{name}' retorna {ret} pero se retorna {ety}")

    def visitBlock(self, ctx):
        self.scopes.append({})
        for s in ctx.statement():
            self.visit(s)
        self.scopes.pop()

    def visitDeclaration(self, ctx):
        declared = self.resolve_tipo(ctx.tipo())
        if ctx.expr() is not None:
            ety = self.visit(ctx.expr())
            if declared.kind == 'dinero' and declared.cur is None and ety.kind == 'dinero':
                declared = money(ety.cur)            # inferir moneda
            elif not ety.bad and self._mixed_currency(declared, ety):
                self.err(ctx.expr(), 'E04',
                         f"no se puede asignar {ety} a '{ctx.ID().getText()}' de tipo {declared}; use convertir()")
            elif not ety.bad and declared != ety:
                self.err(ctx.expr(), 'E03',
                         f"no se puede asignar {ety} a '{ctx.ID().getText()}' de tipo {declared}")
        if declared.kind == 'dinero' and declared.cur is None and ctx.expr() is not None:
            declared = ERR                               # la expresión ya reportó su error
        if declared.kind == 'dinero' and declared.cur is None:
            self.err(ctx.ID(), 'E10',
                     f"'{ctx.ID().getText()}' es 'dinero' pero no tiene moneda (use dinero[PEN] o un valor inicial)")
        self.declare(ctx.ID(), declared)

    def visitAssignment(self, ctx):
        name = ctx.ID().getText()
        target = self.lookup(name)
        ety = self.visit(ctx.expr())
        if target is None:
            self.err(ctx.ID(), 'E01', f"'{name}' no ha sido declarado")
        elif target.kind == 'prestamo':
            self.err(ctx.ID(), 'E09', f"'{name}' es un préstamo y no admite asignación")
        elif target.bad or ety.bad:
            pass
        elif self._mixed_currency(target, ety):
            self.err(ctx.expr(), 'E04', f"no se puede asignar {ety} a '{name}' de tipo {target}; use convertir()")
        elif target != ety:
            self.err(ctx.expr(), 'E03', f"no se puede asignar {ety} a '{name}' de tipo {target}")

    def visitLoanDecl(self, ctx):
        e_monto, e_tea, e_plazo = ctx.expr(0), ctx.expr(1), ctx.expr(2)
        m, t, p = self.visit(e_monto), self.visit(e_tea), self.visit(e_plazo)
        cur = None
        if not m.bad:
            if m.kind != 'dinero':
                self.err(e_monto, 'E03', f"'monto' debe ser dinero, se encontró {m}")
            else:
                cur = m.cur
        if not t.bad and t.kind != 'tasa':
            self.err(e_tea, 'E03', f"'tea' debe ser tasa, se encontró {t}")
        if not p.bad and p.kind != 'num':
            self.err(e_plazo, 'E03', f"'plazo' debe ser num, se encontró {p}")
        # Verificaciones sobre valores constantes (incluye literales negativos como -5%)
        v = self.const_value(e_monto)
        if v is not None and v <= 0:
            self.err(e_monto, 'E07', "el monto del préstamo debe ser positivo")
        v = self.const_value(e_tea)
        if v is not None and (v <= 0 or v > 100):
            motivo = "tasa negativa" if v < 0 else "tasa fuera de rango"
            self.err(e_tea, 'E06', f"la TEA {v:g}% no es válida ({motivo}); debe estar en (0%, 100%]")
        v = self.const_value(e_plazo)
        if v is not None and (v <= 0 or v != int(v)):
            self.err(e_plazo, 'E07', "el plazo debe ser un entero positivo (en meses)")
        vistos = set()
        for x in ctx.loanExtra():
            campo = x.getChild(0).getText()
            e = x.expr()
            ty = self.visit(e)
            if campo in vistos:
                self.err(x, 'E02', f"el campo '{campo}' está repetido en el préstamo '{ctx.ID().getText()}'")
            vistos.add(campo)
            v = self.const_value(e)
            if campo == 'comision':
                if not ty.bad and ty.kind != 'dinero':
                    self.err(e, 'E03', f"'comision' debe ser dinero, se encontró {ty}")
                elif not ty.bad and cur and ty.cur != cur:
                    self.err(e, 'E04', f"la comisión está en {ty.cur} pero el préstamo está en {cur}")
                if v is not None and v < 0:
                    self.err(e, 'E17', "la comisión no puede ser negativa")
            else:
                if not ty.bad and ty.kind != 'tasa':
                    self.err(e, 'E03', f"'seguro' debe ser tasa, se encontró {ty}")
                if v is not None and (v < 0 or v >= 100):
                    self.err(e, 'E17', f"el seguro {v:g}% no es válido; debe estar en [0%, 100%)")
        self.declare(ctx.ID(), Ty('prestamo', cur))

    def visitPrintStmt(self, ctx):
        for e in ctx.expr():
            self.visit(e)

    def _check_cond(self, e):
        ty = self.visit(e)
        if not ty.bad and ty.kind != 'bool':
            self.err(e, 'E08', f"la condición debe ser bool, se encontró {ty}")

    def visitIfStmt(self, ctx):
        self._check_cond(ctx.expr())
        for st in ctx.statement():
            self.scopes.append({})
            self.visit(st)
            self.scopes.pop()

    def visitWhileStmt(self, ctx):
        self._check_cond(ctx.expr())
        self.scopes.append({})
        self.visit(ctx.statement())
        self.scopes.pop()

    def visitForStmt(self, ctx):
        for e in ctx.expr():
            ty = self.visit(e)
            if not ty.bad and ty.kind != 'num':
                self.err(e, 'E03', f"los límites de 'para' deben ser num, se encontró {ty}")
        self.scopes.append({ctx.ID().getText(): NUM})
        self.visit(ctx.statement())
        self.scopes.pop()

    def visitScheduleStmt(self, ctx):
        self.loan_of(ctx.ID())

    # ----------------------------- expresiones ------------------------
    def visitParens(self, ctx):
        return self.visit(ctx.expr())

    def visitUnary(self, ctx):
        a = self.visit(ctx.expr())
        if a.bad:
            return ERR
        if ctx.op.text == '-' and a.kind in ('num', 'dinero', 'tasa'):
            return a
        if ctx.op.text == '!' and a.kind == 'bool':
            return BOOL
        self.err(ctx, 'E05', f"el operador '{ctx.op.text}' no se aplica a {a}")
        return ERR

    def visitMulDiv(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if a.bad or b.bad:
            return ERR
        op = ctx.op.text
        if a.kind == 'num' and b.kind == 'num':
            return NUM
        if op == '*':
            if a.kind == 'dinero' and b.kind in ('num', 'tasa'):
                return a
            if b.kind == 'dinero' and a.kind in ('num', 'tasa'):
                return b
            if {a.kind, b.kind} == {'tasa', 'num'}:
                return TASA
        else:
            if a.kind == 'dinero' and b.kind == 'num':
                return a
            if a.kind == 'dinero' and b.kind == 'dinero':
                if a.cur != b.cur:
                    self.err(ctx, 'E04', f"no se pueden dividir monedas distintas ({a.cur} y {b.cur})")
                    return ERR
                return NUM
            if a.kind == 'tasa' and b.kind == 'num':
                return TASA
        self.err(ctx, 'E05', f"operación '{op}' no válida entre {a} y {b}")
        return ERR

    def visitAddSub(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if a.bad or b.bad:
            return ERR
        if a.kind == 'dinero' and b.kind == 'dinero' and a.cur != b.cur:
            self.err(ctx, 'E04', f"no se pueden mezclar monedas distintas ({a.cur} y {b.cur}); use convertir()")
            return ERR
        if a == b and a.kind in ('num', 'tasa', 'dinero'):
            return a
        self.err(ctx, 'E05', f"operación '{ctx.op.text}' no válida entre {a} y {b}")
        return ERR

    def visitRelational(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if a.bad or b.bad:
            return ERR
        if a.kind == 'dinero' and b.kind == 'dinero' and a.cur != b.cur:
            self.err(ctx, 'E04', f"no se pueden comparar monedas distintas ({a.cur} y {b.cur})")
            return ERR
        if a == b and a.kind in ('num', 'tasa', 'dinero'):
            return BOOL
        self.err(ctx, 'E05', f"comparación '{ctx.op.text}' no válida entre {a} y {b}")
        return ERR

    def visitEquality(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if a.bad or b.bad:
            return ERR
        if a.kind == 'dinero' and b.kind == 'dinero' and a.cur != b.cur:
            self.err(ctx, 'E04', f"no se pueden comparar monedas distintas ({a.cur} y {b.cur})")
            return ERR
        if a == b and a.kind != 'prestamo':
            return BOOL
        self.err(ctx, 'E05', f"comparación '{ctx.op.text}' no válida entre {a} y {b}")
        return ERR

    def _logic(self, ctx, sym):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if a.bad or b.bad:
            return ERR
        if a.kind == 'bool' and b.kind == 'bool':
            return BOOL
        self.err(ctx, 'E05', f"operación '{sym}' requiere bool, se encontró {a} y {b}")
        return ERR

    def visitAndExpr(self, ctx):
        return self._logic(ctx, '&&')

    def visitOrExpr(self, ctx):
        return self._logic(ctx, '||')

    def visitCuotaCall(self, ctx):
        loan = self.loan_of(ctx.ID())
        return money(loan.cur) if loan and loan.cur else ERR

    def visitInteresTotalCall(self, ctx):
        loan = self.loan_of(ctx.ID())
        return money(loan.cur) if loan and loan.cur else ERR

    def visitConvertCall(self, ctx):
        a, rate = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        ok = True
        if not a.bad and a.kind != 'dinero':
            self.err(ctx.expr(0), 'E03', f"convertir() requiere dinero, se encontró {a}")
            ok = False
        if not rate.bad and rate.kind != 'num':
            self.err(ctx.expr(1), 'E03', f"el tipo de cambio debe ser num, se encontró {rate}")
            ok = False
        return money(ctx.CURRENCY().getText()) if ok and not a.bad and not rate.bad else ERR

    def visitTceaCall(self, ctx):
        return TASA if self.loan_of(ctx.ID()) else ERR

    def visitTemCall(self, ctx):
        return TASA if self.loan_of(ctx.ID()) else ERR

    def visitCapitalizarCall(self, ctx):
        c, t, n = (self.visit(e) for e in ctx.expr())
        ok = True
        for ty, want, e, campo in ((c, 'dinero', ctx.expr(0), 'el capital'), (t, 'tasa', ctx.expr(1), 'la tasa'),
                                   (n, 'num', ctx.expr(2), 'el número de periodos')):
            if ty.bad:
                ok = False
            elif ty.kind != want:
                self.err(e, 'E03', f"en capitalizar(), {campo} debe ser {want}, se encontró {ty}")
                ok = False
        return c if ok else ERR

    def visitFuncCall(self, ctx):
        name = ctx.ID().getText()
        args = ctx.argList().expr() if ctx.argList() else []
        atys = [self.visit(a) for a in args]
        if name not in self.funcs:
            if self.lookup(name) is not None:
                self.err(ctx, 'E11', f"'{name}' no es una función")
            else:
                self.err(ctx, 'E11', f"la función '{name}' no ha sido declarada")
            return ERR
        params, ret = self.funcs[name]
        if len(args) != len(params):
            self.err(ctx, 'E12', f"'{name}' espera {len(params)} argumento(s) y recibió {len(args)}")
            return ret
        for i, (a, aty, (pname, pty)) in enumerate(zip(args, atys, params), 1):
            if aty.bad or pty.bad:
                continue
            if self._mixed_currency(pty, aty):
                self.err(a, 'E04', f"argumento {i} de '{name}': se esperaba {pty} y se recibió {aty}; use convertir()")
            elif aty != pty:
                self.err(a, 'E13', f"argumento {i} de '{name}' ('{pname}'): se esperaba {pty} y se recibió {aty}")
        return ret

    def visitMoneyLit(self, ctx):
        return money(ctx.CURRENCY().getText())

    def visitNumLit(self, ctx):
        return NUM

    def visitRateLit(self, ctx):
        return TASA

    def visitBoolLit(self, ctx):
        return BOOL

    def visitStrLit(self, ctx):
        return TEXTO

    def visitVarRef(self, ctx):
        name = ctx.ID().getText()
        ty = self.lookup(name)
        if ty is None:
            self.err(ctx, 'E01', f"'{name}' no ha sido declarado")
            return ERR
        if ty.kind == 'prestamo':
            self.err(ctx, 'E09', f"'{name}' es un préstamo; use cuota({name}) o interesTotal({name})")
            return ERR
        return ty
