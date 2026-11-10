#!/usr/bin/env bash
# Secuencia del video (≤ 5 min). Presiona ENTER entre pasos.
paso() { echo; echo "\$ $*"; read -r _; "$@"; }
clear
echo "== FinLang: demo del compilador (Hito 2) =="; read -r _
# Front end
paso cat tests/valido_03_prestamo.fin
paso python main.py tests/valido_03_prestamo.fin --tokens
paso python main.py tests/err_multiple.fin
paso python main.py tests/err_funciones_multiple.fin
# Back end: LLVM IR y ejecución
paso cat tests/valido_11_prestamo_auto.fin
paso python main.py tests/valido_11_prestamo_auto.fin --ir
paso python main.py tests/valido_03_prestamo.fin --run
paso python main.py tests/valido_08_costos.fin --run
paso python main.py tests/valido_07_funciones.fin --run
paso python main.py tests/err_EJE_tea.fin --run
paso python tools/oraculo.py
paso python run_tests.py
