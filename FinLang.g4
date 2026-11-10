grammar FinLang;

// =====================================================================
//  FinLang - DSL para finanzas personales y préstamos
//  Hito 2 - Teoría de Compiladores 2026-2
// =====================================================================

// ------------------------- ANALIZADOR SINTÁCTICO ---------------------

// Las funciones solo se declaran en el nivel superior (no hay funciones anidadas)
program : topLevel* EOF ;

topLevel
    : funcDecl
    | statement
    ;

// funcion cuotaConSeguro(dinero[PEN] c, tasa s): dinero[PEN] { retornar c + c * s; }
funcDecl  : FUNCION ID LPAREN paramList? RPAREN COLON tipo block ;
paramList : param (COMMA param)* ;
param     : tipo ID ;

statement
    : declaration
    | assignment
    | loanDecl
    | printStmt
    | ifStmt
    | whileStmt
    | forStmt
    | scheduleStmt
    | returnStmt
    | block
    ;

block : LBRACE statement* RBRACE ;

// dinero saldo = 1500 PEN;   dinero[USD] ahorro;   num n = 3;
declaration : tipo ID (ASSIGN expr)? SEMI ;

tipo
    : TNUM
    | TDINERO (LBRACK CURRENCY RBRACK)?
    | TTASA
    | TBOOL
    ;

assignment : ID ASSIGN expr SEMI ;

// Construcción propia del dominio: préstamo.
// monto, tea y plazo son obligatorios y van en ese orden; comision (dinero fijo
// por cuota) y seguro (tasa mensual sobre el saldo, p. ej. desgravamen) son
// opcionales y solo afectan el pago total y la TCEA.
loanDecl
    : PRESTAMO ID LBRACE
        MONTO COLON expr SEMI
        TEA   COLON expr SEMI
        PLAZO COLON expr SEMI
        loanExtra*
      RBRACE
    ;

loanExtra
    : COMISION COLON expr SEMI      # comisionField
    | SEGURO   COLON expr SEMI      # seguroField
    ;

printStmt    : MOSTRAR expr (COMMA expr)* SEMI ;
ifStmt       : SI LPAREN expr RPAREN statement (SINO statement)? ;
whileStmt    : MIENTRAS LPAREN expr RPAREN statement ;
forStmt      : PARA ID DESDE expr HASTA expr statement ;
scheduleStmt : CRONOGRAMA ID SEMI ;

returnStmt   : RETORNAR expr SEMI ;

// Else colgante: 'si (a) si (b) x; sino y;' es ambigua en esta gramática.
// ANTLR4 la resuelve de forma voraz: el 'sino' se asocia al 'si' más cercano
// (el mismo criterio de C y Java). Ver tests/valido_10_else_colgante.fin.

argList : expr (COMMA expr)* ;

// La precedencia la define el orden de las alternativas (mayor a menor)
expr
    : LPAREN expr RPAREN                                       # parens
    | op=(MINUS | NOT) expr                                    # unary
    | expr op=(MUL | DIV) expr                                 # mulDiv
    | expr op=(PLUS | MINUS) expr                              # addSub
    | expr op=(LT | LE | GT | GE) expr                         # relational
    | expr op=(EQ | NEQ) expr                                  # equality
    | expr AND expr                                            # andExpr
    | expr OR expr                                             # orExpr
    | CUOTA LPAREN ID RPAREN                                   # cuotaCall
    | INTERES_TOTAL LPAREN ID RPAREN                           # interesTotalCall
    | CONVERTIR LPAREN expr COMMA CURRENCY COMMA expr RPAREN   # convertCall
    | TCEA LPAREN ID RPAREN                                    # tceaCall
    | TASA_MENSUAL LPAREN ID RPAREN                            # temCall
    | CAPITALIZAR LPAREN expr COMMA expr COMMA expr RPAREN     # capitalizarCall
    | ID LPAREN argList? RPAREN                                # funcCall
    | NUMERO CURRENCY                                          # moneyLit
    | NUMERO                                                   # numLit
    | PORCENTAJE                                               # rateLit
    | (TRUE | FALSE)                                           # boolLit
    | STRING                                                   # strLit
    | ID                                                       # varRef
    ;

// --------------------------- ANALIZADOR LÉXICO -----------------------

// Tipos
TNUM     : 'num' ;
TDINERO  : 'dinero' ;
TTASA    : 'tasa' ;
TBOOL    : 'bool' ;

// Palabras clave
PRESTAMO       : 'prestamo' ;
MONTO          : 'monto' ;
TEA            : 'tea' ;
PLAZO          : 'plazo' ;
SI             : 'si' ;
SINO           : 'sino' ;
MIENTRAS       : 'mientras' ;
PARA           : 'para' ;
DESDE          : 'desde' ;
HASTA          : 'hasta' ;
MOSTRAR        : 'mostrar' ;
CRONOGRAMA     : 'cronograma' ;
CUOTA          : 'cuota' ;
INTERES_TOTAL  : 'interesTotal' ;
CONVERTIR      : 'convertir' ;
TCEA           : 'tcea' ;
TASA_MENSUAL   : 'tasaMensual' ;
CAPITALIZAR    : 'capitalizar' ;
COMISION       : 'comision' ;
SEGURO         : 'seguro' ;
FUNCION        : 'funcion' ;
RETORNAR       : 'retornar' ;
TRUE           : 'verdadero' ;
FALSE          : 'falso' ;

// Monedas
CURRENCY : 'PEN' | 'USD' | 'EUR' ;

// Operadores
PLUS   : '+' ;
MINUS  : '-' ;
MUL    : '*' ;
DIV    : '/' ;
LT     : '<' ;
LE     : '<=' ;
GT     : '>' ;
GE     : '>=' ;
EQ     : '==' ;
NEQ    : '!=' ;
AND    : '&&' ;
OR     : '||' ;
NOT    : '!' ;
ASSIGN : '=' ;

// Delimitadores
LPAREN : '(' ;
RPAREN : ')' ;
LBRACE : '{' ;
RBRACE : '}' ;
LBRACK : '[' ;
RBRACK : ']' ;
SEMI   : ';' ;
COMMA  : ',' ;
COLON  : ':' ;

// Literales e identificadores
PORCENTAJE : DIGITO+ ('.' DIGITO+)? '%' ;
NUMERO     : DIGITO+ ('.' DIGITO+)? ;
STRING     : '"' ~["\r\n]* '"' ;
ID         : [a-zA-Z_] [a-zA-Z_0-9]* ;

fragment DIGITO : [0-9] ;

// Se ignoran
LINE_COMMENT  : '//' ~[\r\n]* -> skip ;
BLOCK_COMMENT : '/*' .*? '*/' -> skip ;
WS            : [ \t\r\n]+ -> skip ;

// Cualquier otro carácter: se reporta como error léxico
ERROR_CHAR : . ;
