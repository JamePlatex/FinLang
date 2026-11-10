#!/usr/bin/env bash
# Descarga ANTLR, instala dependencias y genera el lexer/parser en ./gen
set -e
JAR=antlr-4.13.1-complete.jar
[ -f "$JAR" ] || curl -fL -o "$JAR" https://www.antlr.org/download/$JAR \
  || curl -fL -o "$JAR" https://repo1.maven.org/maven2/org/antlr/antlr4/4.13.1/antlr4-4.13.1-complete.jar
pip install -r requirements.txt
java -jar "$JAR" -Dlanguage=Python3 -visitor -no-listener -o gen FinLang.g4
echo "Listo. Prueba con: python run_tests.py"
