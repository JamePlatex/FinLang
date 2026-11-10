# FinLang — DSL para finanzas personales y préstamos

Compilador con **ANTLR4 + Python** (front end) y **LLVM IR vía llvmlite** (back end).

- Hito 1: analizador léxico, sintáctico y semántico (E01–E10).
- Hito 2: gramática ampliada (funciones, `retornar`, comisión y seguro, `tcea`, `tasaMensual`,
  `capitalizar`), semántico completo (E01–E17) y generación de LLVM IR con ejecución JIT.

## Requisitos
- Java 11+ y Python 3.10+
- `antlr-4.13.1-complete.jar` y `pip install -r requirements.txt` (antlr4 runtime, llvmlite, numpy-financial)

## Puesta en marcha
    ./setup.sh                      # descarga ANTLR, instala dependencias y genera gen/
    # o a mano:
    java -jar antlr-4.13.1-complete.jar -Dlanguage=Python3 -visitor -no-listener -o gen FinLang.g4

## Uso
    python main.py prog.fin                 # análisis léxico, sintáctico y semántico
    python main.py prog.fin --tokens        # tokens (analizador léxico)
    python main.py prog.fin --tree          # árbol sintáctico
    python main.py prog.fin --ir [out.ll]   # LLVM IR generado (pantalla o archivo; sirve con lli/clang)
    python main.py prog.fin --run           # genera LLVM IR y lo ejecuta con JIT
    python main.py prog.fin --obj out.o     # código objeto nativo; enlazar: cc out.o -lm -o prog
    python run_tests.py                     # todas las pruebas (front end, ejecución y numéricas)
    python run_tests.py --solo-frontend     # solo los códigos de error, como en el Hito 1
    python tools/oraculo.py                 # cálculo independiente con numpy-financial
    ./demo.sh                               # secuencia del video

## Ejemplo
    prestamo auto { monto: 30000 USD; tea: 12%; plazo: 36; }
    mostrar "Cuota:", cuota(auto);              // Cuota: 987.66 USD
    mostrar "Interés total:", interesTotal(auto); // Interés total: 5555.84 USD
    mostrar "TCEA:", tcea(auto);                // TCEA: 12%
    cronograma auto;                            // tabla de 36 cuotas

    prestamo consumo { monto: 10000 PEN; tea: 20%; plazo: 12; comision: 10 PEN; seguro: 0.08%; }
    mostrar tcea(consumo);                      // 23.6549%

    funcion doble(num n): num { retornar n * 2; }

## Modelo financiero
- `tea` es la tasa efectiva anual. TEM = (1 + TEA)^(1/12) − 1.
- `cuota(p)`: método francés, R = P·i / (1 − (1 + i)^−n), con i = TEM.
- `interesTotal(p)` = R·n − P.
- `comision` (opcional): monto fijo por cuota. `seguro` (opcional): % mensual sobre el saldo (desgravamen).
- `tcea(p)`: TIR mensual de los pagos totales (cuota + comisión + seguro), anualizada: (1 + r)^12 − 1.
- `capitalizar(C, t, n)` = C·(1 + t)^n.

## Errores
Léxicos `[LEX]`, sintácticos `[SIN]`, en ejecución `[EJE]` (división entre cero, préstamo inválido
calculado a partir de variables). Semánticos:

E01 variable no declarada · E02 duplicado · E03 tipos incompatibles · E04 mezcla de monedas ·
E05 operación inválida · E06 tasa fuera de (0%,100%] · E07 monto/plazo inválido ·
E08 condición no booleana · E09 no es un préstamo · E10 dinero sin moneda ·
E11 función no declarada · E12 número de argumentos · E13 tipo de argumento ·
E14 tipo de retorno · E15 `retornar` fuera de función · E16 no retorna en todos los caminos ·
E17 comisión o seguro inválido.

## Estructura
- `FinLang.g4` gramática léxica y sintáctica (ANTLR4) · `gen/` lexer y parser generados
- `semantic.py` analizador semántico (tabla de símbolos por ámbito, tipos con moneda, firmas de funciones)
- `codegen.py` generador de LLVM IR (llvmlite), ejecución JIT y código objeto
- `main.py` driver · `run_tests.py` + `tests/` (`// ESPERA: ...`, `// SALIDA: ...`) · `tests/numericos.py`
- `tools/derivaciones.py` derivaciones más a la izquierda · `tools/oraculo.py` oráculo numérico
- `docs/` informe, presentación, derivaciones, guion del video
