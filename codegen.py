"""Generador de código LLVM IR para FinLang (back end, Hito 2).

Recorre el árbol de ANTLR4 ya validado por el analizador semántico y construye
un módulo LLVM con llvmlite. Decisiones de representación:
  - num, tasa y dinero  -> double. La moneda solo existe en compilación: el
    semántico ya garantizó que no se mezclan, así que en el IR se borra.
  - tasa se guarda como fracción (12% -> 0.12).
  - bool -> i1.
  - prestamo -> struct {monto, tea, plazo, comision, seguro} (5 double).
  - Variables del nivel superior -> variables globales (visibles en funciones).
    Variables de bloques y de funciones -> alloca en la pila.
  - Las rutinas financieras (TEM, cuota francesa, interés total, TCEA y
    cronograma) se generan como funciones internas del mismo módulo.
  - Errores en ejecución (división entre cero, préstamo inválido calculado en
    tiempo de ejecución) imprimen "[EJE] ..." y terminan con exit(1).
"""
from llvmlite import ir

from FinLangParser import FinLangParser as P
from FinLangVisitor import FinLangVisitor

DBL = ir.DoubleType()
I1 = ir.IntType(1)
I8 = ir.IntType(8)
I32 = ir.IntType(32)
I8P = I8.as_pointer()
LOAN = ir.LiteralStructType([DBL] * 5)          # monto, tea, plazo, comision, seguro
ARG_NAMES = {'fl_tem': ['tea'], 'fl_cuota': ['P', 'i', 'n'], 'fl_tcea': ['P', 'i', 'n', 'comision', 'seguro'],
             'fl_cronograma': ['P', 'i', 'n', 'comision', 'seguro', 'moneda']}
CAMPOS = {'monto': 0, 'tea': 1, 'plazo': 2, 'comision': 3, 'seguro': 4}


def llty(ty):
    return I1 if ty.kind == 'bool' else DBL


def c(x):
    return ir.Constant(DBL, float(x))


class CodeGen(FinLangVisitor):
    def __init__(self, sema, name="finlang"):
        self.sema = sema
        self.m = ir.Module(name=name)
        import llvmlite.binding as llvm
        self.m.triple = llvm.get_process_triple()     # el .ll queda listo para lli / clang
        self.strings = {}
        self.scopes = [{}]
        self.loan_cur = {}               # puntero del préstamo -> moneda (texto)
        self.uid = 0
        self._decl_runtime()
        self.main = ir.Function(self.m, ir.FunctionType(I32, []), name="main")
        self.fn = self.main
        self.b = ir.IRBuilder(self.main.append_basic_block("entry"))

    # ============================ utilidades ============================
    def _decl_runtime(self):
        m = self.m
        self.printf = ir.Function(m, ir.FunctionType(I32, [I8P], var_arg=True), name="printf")
        self.exit = ir.Function(m, ir.FunctionType(ir.VoidType(), [I32]), name="exit")
        self.fflush = ir.Function(m, ir.FunctionType(I32, [I8P]), name="fflush")
        self.pow = m.declare_intrinsic('llvm.pow', [DBL])
        self.fabs = m.declare_intrinsic('llvm.fabs', [DBL])
        self.floor = m.declare_intrinsic('llvm.floor', [DBL])
        self.rt = {}

    def cstr(self, text):
        """Puntero i8* a una cadena constante global (terminada en \\0)."""
        if text not in self.strings:
            data = bytearray(text.encode('utf-8')) + b'\0'
            arr = ir.ArrayType(I8, len(data))
            g = ir.GlobalVariable(self.m, arr, name=f".str{len(self.strings)}")
            g.linkage, g.global_constant = 'private', True
            g.initializer = ir.Constant(arr, data)
            self.strings[text] = g
        return self.b.bitcast(self.strings[text], I8P)

    def print(self, fmt, *args):
        self.b.call(self.printf, [self.cstr(fmt), *args])

    def entry_alloca(self, ty, name):
        """alloca en el bloque de entrada de la función actual (buena práctica en LLVM)."""
        entry = self.fn.entry_basic_block
        if self.b.block is entry:          # el builder de llvmlite usa un índice: no insertar antes de él
            return self.b.alloca(ty, name=name)
        tmp = ir.IRBuilder(entry)
        if entry.instructions:
            tmp.position_before(entry.instructions[0])
        return tmp.alloca(ty, name=name)

    def storage(self, name, ty):
        """Crea el almacenamiento de una variable según su ámbito."""
        self.uid += 1
        if self.fn is self.main and len(self.scopes) == 1:
            g = ir.GlobalVariable(self.m, ty, name=f"{name}.{self.uid}")
            g.linkage = 'internal'
            g.initializer = ir.Constant(ty, None)
            return g
        return self.entry_alloca(ty, name)

    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        raise KeyError(name)          # no ocurre: el semántico ya lo verificó

    def ty(self, e):
        return self.sema.types[e]

    def runtime_error(self, cond, node, msg):
        """Si cond (i1) es verdadera: imprime [EJE] y termina el programa."""
        tok = node.start
        with self.b.if_then(cond, likely=False):
            self.print(f"[EJE] Línea {tok.line}:{tok.column + 1} - {msg}\n")
            self.b.call(self.fflush, [ir.Constant(I8P, None)])
            self.b.call(self.exit, [ir.Constant(I32, 1)])

    def new_block(self, name):
        return self.fn.append_basic_block(name)

    def loop(self, b, start, end, body):
        """for k = start .. end (double, inclusivo) generado con el builder b."""
        fn = b.function
        k = self.entry_alloca(DBL, "k")
        b.store(start, k)
        cond, cuerpo, fin = fn.append_basic_block("l.cond"), fn.append_basic_block("l.body"), fn.append_basic_block("l.end")
        b.branch(cond)
        b.position_at_end(cond)
        b.cbranch(b.fcmp_ordered('<=', b.load(k), end), cuerpo, fin)
        b.position_at_end(cuerpo)
        body(b.load(k))
        b.store(b.fadd(b.load(k), c(1)), k)
        b.branch(cond)
        b.position_at_end(fin)

    # ======================= rutinas financieras ========================
    def _rt(self, name, args, build):
        if name not in self.rt:
            f = ir.Function(self.m, ir.FunctionType(DBL if name != 'fl_cronograma' else ir.VoidType(), args), name=name)
            f.linkage = 'internal'
            for arg, nombre in zip(f.args, ARG_NAMES[name]):
                arg.name = nombre
            b = ir.IRBuilder(f.append_basic_block("entry"))
            saved, (self.b, self.fn) = (self.b, self.fn), (b, f)
            build(f, b)
            self.b, self.fn = saved
            self.rt[name] = f
        return self.rt[name]

    def rt_tem(self):
        # TEM = (1 + TEA)^(1/12) - 1   (tasa efectiva mensual equivalente)
        def build(f, b):
            b.ret(b.fsub(b.call(self.pow, [b.fadd(c(1), f.args[0]), c(1 / 12)]), c(1)))
        return self._rt('fl_tem', [DBL], build)

    def rt_cuota(self):
        # Método francés: R = P * i / (1 - (1 + i)^-n)
        def build(f, b):
            p, i, n = f.args
            den = b.fsub(c(1), b.call(self.pow, [b.fadd(c(1), i), b.fneg(n)]))
            b.ret(b.fdiv(b.fmul(p, i), den))
        return self._rt('fl_cuota', [DBL, DBL, DBL], build)

    def rt_tcea(self):
        # TIR mensual r de: monto = sum_k pago_k / (1 + r)^k, por bisección en [0, 1].
        # pago_k = cuota + comision + seguro * saldo_{k-1};  TCEA = (1 + r)^12 - 1
        def build(f, b):
            p, i, n, com, seg = f.args
            cuota = b.call(self.rt_cuota(), [p, i, n])
            lo, hi = b.alloca(DBL), b.alloca(DBL)
            saldo, suma = b.alloca(DBL), b.alloca(DBL)
            b.store(c(0), lo); b.store(c(1), hi)

            def biseccion(_):
                r = b.fmul(c(0.5), b.fadd(b.load(lo), b.load(hi)))
                b.store(p, saldo); b.store(c(0), suma)

                def mes(k):
                    s = b.load(saldo)
                    pago = b.fadd(b.fadd(cuota, com), b.fmul(seg, s))
                    desc = b.call(self.pow, [b.fadd(c(1), r), k])
                    b.store(b.fadd(b.load(suma), b.fdiv(pago, desc)), suma)
                    b.store(b.fsub(s, b.fsub(cuota, b.fmul(s, i))), saldo)
                self.loop(b, c(1), n, mes)
                vpn = b.fsub(b.load(suma), p)            # decrece con r
                pos = b.fcmp_ordered('>', vpn, c(0))
                b.store(b.select(pos, r, b.load(lo)), lo)
                b.store(b.select(pos, b.load(hi), r), hi)
            self.loop(b, c(1), c(200), biseccion)
            r = b.fmul(c(0.5), b.fadd(b.load(lo), b.load(hi)))
            b.ret(b.fsub(b.call(self.pow, [b.fadd(c(1), r), c(12)]), c(1)))
        return self._rt('fl_tcea', [DBL] * 5, build)

    def rt_cronograma(self):
        def build(f, b):
            p, i, n, com, seg, cur = f.args
            cuota = b.call(self.rt_cuota(), [p, i, n])
            saldo, t_int, t_pago = b.alloca(DBL), b.alloca(DBL), b.alloca(DBL)
            b.store(p, saldo); b.store(c(0), t_int); b.store(c(0), t_pago)
            self.print("%4s %14s %12s %14s %12s %12s %14s %14s\n", self.cstr("Mes"), self.cstr("Saldo inicial"),
                       self.cstr("Interés "), self.cstr("Amortización "), self.cstr("Cuota"), self.cstr("Costos"),
                       self.cstr("Pago total"), self.cstr("Saldo final"))

            def mes(k):
                s = b.load(saldo)
                interes = b.fmul(s, i)
                amort = b.fsub(cuota, interes)
                costos = b.fadd(com, b.fmul(seg, s))
                pago = b.fadd(cuota, costos)
                fin = b.fsub(s, amort)
                fin = b.select(b.fcmp_ordered('<', b.call(self.fabs, [fin]), c(0.005)), c(0), fin)
                self.print("%4.0f %14.2f %12.2f %14.2f %12.2f %12.2f %14.2f %14.2f\n",
                           k, s, interes, amort, cuota, costos, pago, fin)
                b.store(fin, saldo)
                b.store(b.fadd(b.load(t_int), interes), t_int)
                b.store(b.fadd(b.load(t_pago), pago), t_pago)
            self.loop(b, c(1), n, mes)
            self.print("Total intereses: %.2f %s   Total pagado: %.2f %s\n", b.load(t_int), cur, b.load(t_pago), cur)
            b.ret_void()
        return self._rt('fl_cronograma', [DBL] * 5 + [I8P], build)

    def loan_fields(self, id_node):
        ptr = self.lookup(id_node.getText())
        vals = [self.b.load(self.b.gep(ptr, [ir.Constant(I32, 0), ir.Constant(I32, k)])) for k in range(5)]
        tem = self.b.call(self.rt_tem(), [vals[1]])
        return ptr, vals, tem

    # ============================ programa ==============================
    def generate(self, tree):
        # Pasada previa: declarar todas las funciones (recursión y uso antes de definir)
        self.funcs = {}
        for name, (params, ret) in self.sema.funcs.items():
            ft = ir.FunctionType(llty(ret), [llty(t) for _, t in params])
            self.funcs[name] = ir.Function(self.m, ft, name=f"fn.{name}")
        self.visit(tree)
        self.b.call(self.fflush, [ir.Constant(I8P, None)])
        self.b.ret(ir.Constant(I32, 0))
        return self.m

    def visitProgram(self, ctx):
        for top in ctx.topLevel():
            self.visit(top.getChild(0))

    def visitFuncDecl(self, ctx):
        name = ctx.ID().getText()
        fn = self.funcs[name]
        if fn.blocks:                     # duplicada (no ocurre si no hubo errores)
            return
        params, ret = self.sema.funcs[name]
        saved = (self.fn, self.b, self.scopes)
        self.fn, self.b = fn, ir.IRBuilder(fn.append_basic_block("entry"))
        self.scopes = [self.scopes[0], {}]
        for arg, (pname, pty) in zip(fn.args, params):
            arg.name = pname
            slot = self.entry_alloca(llty(pty), pname)
            self.b.store(arg, slot)
            self.scopes[-1][pname] = slot
        for st in ctx.block().statement():
            self.visit(st)
        if not self.b.block.is_terminated:   # inalcanzable (E16 lo garantiza); LLVM exige terminador
            self.b.ret(ir.Constant(llty(ret), 0 if ret.kind == 'bool' else 0.0))
        self.fn, self.b, self.scopes = saved

    def visitReturnStmt(self, ctx):
        self.b.ret(self.visit(ctx.expr()))
        self.b.position_at_end(self.new_block("tras.retornar"))   # código muerto posterior

    # ============================ sentencias ============================
    def visitBlock(self, ctx):
        self.scopes.append({})
        for st in ctx.statement():
            self.visit(st)
        self.scopes.pop()

    def visitDeclaration(self, ctx):
        name = ctx.ID().getText()
        kind = 'bool' if ctx.tipo().TBOOL() else 'x'
        t = I1 if kind == 'bool' else DBL
        slot = self.storage(name, t)
        val = self.visit(ctx.expr()) if ctx.expr() else ir.Constant(t, 0 if t is I1 else 0.0)
        self.b.store(val, slot)
        self.scopes[-1][name] = slot

    def visitAssignment(self, ctx):
        val = self.visit(ctx.expr())
        self.b.store(val, self.lookup(ctx.ID().getText()))

    def visitLoanDecl(self, ctx):
        name = ctx.ID().getText()
        slot = self.storage(name, LOAN)
        vals = {'monto': self.visit(ctx.expr(0)), 'tea': self.visit(ctx.expr(1)),
                'plazo': self.visit(ctx.expr(2)), 'comision': c(0), 'seguro': c(0)}
        for x in ctx.loanExtra():
            vals[x.getChild(0).getText()] = self.visit(x.expr())
        # Validación en ejecución de lo que el semántico no pudo ver (valores no constantes)
        b = self.b
        self.runtime_error(b.fcmp_ordered('<=', vals['monto'], c(0)), ctx.expr(0),
                           "E07: el monto del préstamo debe ser positivo")
        tea = vals['tea']
        self.runtime_error(b.or_(b.fcmp_unordered('<=', tea, c(0)), b.fcmp_ordered('>', tea, c(1))), ctx.expr(1),
                           "E06: la TEA debe estar en (0%, 100%]")
        pl = vals['plazo']
        self.runtime_error(b.or_(b.fcmp_unordered('<=', pl, c(0)), b.fcmp_unordered('!=', pl, b.call(self.floor, [pl]))),
                           ctx.expr(2), "E07: el plazo debe ser un entero positivo (en meses)")
        for campo, k in CAMPOS.items():
            b.store(vals[campo], b.gep(slot, [ir.Constant(I32, 0), ir.Constant(I32, k)]))
        self.loan_cur[name] = self.ty(ctx.expr(0)).cur
        self.scopes[-1][name] = slot

    def visitPrintStmt(self, ctx):
        fmt, args = [], []
        for e in ctx.expr():
            ty = self.ty(e)
            if isinstance(e, P.StrLitContext):
                fmt.append("%s")
                args.append(self.cstr(e.STRING().getText()[1:-1]))
                continue
            v = self.visit(e)
            if ty.kind == 'bool':
                fmt.append("%s")
                args.append(self.b.select(v, self.cstr("verdadero"), self.cstr("falso")))
            elif ty.kind == 'dinero':
                fmt.append(f"%.2f {ty.cur}")
                args.append(v)
            elif ty.kind == 'tasa':
                fmt.append("%.6g%%")
                args.append(self.b.fmul(v, c(100)))
            else:
                fmt.append("%.10g")
                args.append(v)
        self.print(" ".join(fmt) + "\n", *args)

    def visitScheduleStmt(self, ctx):
        name = ctx.ID().getText()
        _, v, tem = self.loan_fields(ctx.ID())
        cur = self.loan_cur.get(name, "")
        self.print(f"Cronograma de '{name}' ({cur}): monto %.2f, TEA %.2f%%, TEM %.4f%%, plazo %.0f meses\n",
                   v[0], self.b.fmul(v[1], c(100)), self.b.fmul(tem, c(100)), v[2])
        self.b.call(self.rt_cronograma(), [v[0], tem, v[2], v[3], v[4], self.cstr(cur)])

    def _cond(self, e):
        return self.visit(e)

    def visitIfStmt(self, ctx):
        cond = self._cond(ctx.expr())
        sts = ctx.statement()
        then_bb, merge = self.new_block("si.entonces"), None
        else_bb = self.new_block("si.sino") if len(sts) == 2 else None
        merge = self.new_block("si.fin")
        self.b.cbranch(cond, then_bb, else_bb or merge)
        for st, bb in ((sts[0], then_bb),) + (((sts[1], else_bb),) if else_bb else ()):
            self.b.position_at_end(bb)
            self.scopes.append({})
            self.visit(st)
            self.scopes.pop()
            if not self.b.block.is_terminated:
                self.b.branch(merge)
        self.b.position_at_end(merge)

    def visitWhileStmt(self, ctx):
        cond_bb, body_bb, end_bb = self.new_block("mq.cond"), self.new_block("mq.cuerpo"), self.new_block("mq.fin")
        self.b.branch(cond_bb)
        self.b.position_at_end(cond_bb)
        self.b.cbranch(self._cond(ctx.expr()), body_bb, end_bb)
        self.b.position_at_end(body_bb)
        self.scopes.append({})
        self.visit(ctx.statement())
        self.scopes.pop()
        if not self.b.block.is_terminated:
            self.b.branch(cond_bb)
        self.b.position_at_end(end_bb)

    def visitForStmt(self, ctx):
        # para i desde a hasta b S   (inclusivo, paso 1; 'hasta' se evalúa una vez)
        name = ctx.ID().getText()
        i = self.entry_alloca(DBL, name)
        self.b.store(self.visit(ctx.expr(0)), i)
        hasta = self.visit(ctx.expr(1))
        cond_bb, body_bb, end_bb = self.new_block("para.cond"), self.new_block("para.cuerpo"), self.new_block("para.fin")
        self.b.branch(cond_bb)
        self.b.position_at_end(cond_bb)
        self.b.cbranch(self.b.fcmp_ordered('<=', self.b.load(i), hasta), body_bb, end_bb)
        self.b.position_at_end(body_bb)
        self.scopes.append({name: i})
        self.visit(ctx.statement())
        self.scopes.pop()
        if not self.b.block.is_terminated:
            self.b.store(self.b.fadd(self.b.load(i), c(1)), i)
            self.b.branch(cond_bb)
        self.b.position_at_end(end_bb)

    # ============================ expresiones ===========================
    def visitParens(self, ctx):
        return self.visit(ctx.expr())

    def visitUnary(self, ctx):
        v = self.visit(ctx.expr())
        return self.b.fneg(v) if ctx.op.text == '-' else self.b.not_(v)

    def visitMulDiv(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if ctx.op.text == '*':
            return self.b.fmul(a, b)
        self.runtime_error(self.b.fcmp_ordered('==', b, c(0)), ctx, "división entre cero")
        return self.b.fdiv(a, b)

    def visitAddSub(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        return self.b.fadd(a, b) if ctx.op.text == '+' else self.b.fsub(a, b)

    def visitRelational(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        return self.b.fcmp_ordered(ctx.op.text, a, b)

    def visitEquality(self, ctx):
        a, b = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        if a.type == I1:
            return self.b.icmp_unsigned(ctx.op.text, a, b)
        return self.b.fcmp_ordered(ctx.op.text, a, b) if ctx.op.text == '==' else self.b.fcmp_unordered('!=', a, b)

    def _short_circuit(self, ctx, is_and):
        # Evaluación en cortocircuito: a && b no evalúa b si a es falso.
        a = self.visit(ctx.expr(0))
        start = self.b.block
        rhs_bb, end_bb = self.new_block("sc.der"), self.new_block("sc.fin")
        if is_and:
            self.b.cbranch(a, rhs_bb, end_bb)
        else:
            self.b.cbranch(a, end_bb, rhs_bb)
        self.b.position_at_end(rhs_bb)
        bval = self.visit(ctx.expr(1))
        rhs_end = self.b.block
        self.b.branch(end_bb)
        self.b.position_at_end(end_bb)
        phi = self.b.phi(I1)
        phi.add_incoming(ir.Constant(I1, 0 if is_and else 1), start)
        phi.add_incoming(bval, rhs_end)
        return phi

    def visitAndExpr(self, ctx):
        return self._short_circuit(ctx, True)

    def visitOrExpr(self, ctx):
        return self._short_circuit(ctx, False)

    def visitCuotaCall(self, ctx):
        _, v, tem = self.loan_fields(ctx.ID())
        return self.b.call(self.rt_cuota(), [v[0], tem, v[2]])

    def visitInteresTotalCall(self, ctx):
        _, v, tem = self.loan_fields(ctx.ID())
        cuota = self.b.call(self.rt_cuota(), [v[0], tem, v[2]])
        return self.b.fsub(self.b.fmul(cuota, v[2]), v[0])

    def visitTemCall(self, ctx):
        return self.loan_fields(ctx.ID())[2]

    def visitTceaCall(self, ctx):
        _, v, tem = self.loan_fields(ctx.ID())
        return self.b.call(self.rt_tcea(), [v[0], tem, v[2], v[3], v[4]])

    def visitConvertCall(self, ctx):
        # convertir(x, MONEDA, tc) = x * tc   (tc: unidades de MONEDA por unidad de origen)
        x, tc = self.visit(ctx.expr(0)), self.visit(ctx.expr(1))
        self.runtime_error(self.b.fcmp_unordered('<=', tc, c(0)), ctx.expr(1), "el tipo de cambio debe ser positivo")
        return self.b.fmul(x, tc)

    def visitCapitalizarCall(self, ctx):
        # Interés compuesto: C * (1 + t)^n
        cap, t, n = (self.visit(e) for e in ctx.expr())
        return self.b.fmul(cap, self.b.call(self.pow, [self.b.fadd(c(1), t), n]))

    def visitFuncCall(self, ctx):
        args = [self.visit(a) for a in (ctx.argList().expr() if ctx.argList() else [])]
        return self.b.call(self.funcs[ctx.ID().getText()], args)

    def visitMoneyLit(self, ctx):
        return c(ctx.NUMERO().getText())

    def visitNumLit(self, ctx):
        return c(ctx.NUMERO().getText())

    def visitRateLit(self, ctx):
        return c(float(ctx.PORCENTAJE().getText()[:-1]) / 100)

    def visitBoolLit(self, ctx):
        return ir.Constant(I1, 1 if ctx.TRUE() else 0)

    def visitVarRef(self, ctx):
        return self.b.load(self.lookup(ctx.ID().getText()))


# ============================== ejecución ===============================
def compile_ir(module, opt=0, reloc='default'):
    import llvmlite.binding as llvm
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    mod = llvm.parse_assembly(str(module))
    mod.verify()
    tm = llvm.Target.from_default_triple().create_target_machine(opt=opt, reloc=reloc)
    return llvm, mod, tm


def run_jit(module):
    """Compila el módulo con MCJIT y ejecuta main(). Devuelve el código de salida."""
    import ctypes
    llvm, mod, tm = compile_ir(module)
    engine = llvm.create_mcjit_compiler(mod, tm)
    engine.finalize_object()
    engine.run_static_constructors()
    main = ctypes.CFUNCTYPE(ctypes.c_int)(engine.get_function_address("main"))
    return main()


def emit_object(module, path):
    llvm, mod, tm = compile_ir(module, opt=2, reloc='pic')
    with open(path, "wb") as f:
        f.write(tm.emit_object(mod))
