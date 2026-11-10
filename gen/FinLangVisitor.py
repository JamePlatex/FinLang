# Generated from FinLang.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .FinLangParser import FinLangParser
else:
    from FinLangParser import FinLangParser

# This class defines a complete generic visitor for a parse tree produced by FinLangParser.

class FinLangVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by FinLangParser#program.
    def visitProgram(self, ctx:FinLangParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#topLevel.
    def visitTopLevel(self, ctx:FinLangParser.TopLevelContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#funcDecl.
    def visitFuncDecl(self, ctx:FinLangParser.FuncDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#paramList.
    def visitParamList(self, ctx:FinLangParser.ParamListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#param.
    def visitParam(self, ctx:FinLangParser.ParamContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#statement.
    def visitStatement(self, ctx:FinLangParser.StatementContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#block.
    def visitBlock(self, ctx:FinLangParser.BlockContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#declaration.
    def visitDeclaration(self, ctx:FinLangParser.DeclarationContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#tipo.
    def visitTipo(self, ctx:FinLangParser.TipoContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#assignment.
    def visitAssignment(self, ctx:FinLangParser.AssignmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#loanDecl.
    def visitLoanDecl(self, ctx:FinLangParser.LoanDeclContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#comisionField.
    def visitComisionField(self, ctx:FinLangParser.ComisionFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#seguroField.
    def visitSeguroField(self, ctx:FinLangParser.SeguroFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#printStmt.
    def visitPrintStmt(self, ctx:FinLangParser.PrintStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#ifStmt.
    def visitIfStmt(self, ctx:FinLangParser.IfStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#whileStmt.
    def visitWhileStmt(self, ctx:FinLangParser.WhileStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#forStmt.
    def visitForStmt(self, ctx:FinLangParser.ForStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#scheduleStmt.
    def visitScheduleStmt(self, ctx:FinLangParser.ScheduleStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#returnStmt.
    def visitReturnStmt(self, ctx:FinLangParser.ReturnStmtContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#argList.
    def visitArgList(self, ctx:FinLangParser.ArgListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#parens.
    def visitParens(self, ctx:FinLangParser.ParensContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#moneyLit.
    def visitMoneyLit(self, ctx:FinLangParser.MoneyLitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#tceaCall.
    def visitTceaCall(self, ctx:FinLangParser.TceaCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#numLit.
    def visitNumLit(self, ctx:FinLangParser.NumLitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#rateLit.
    def visitRateLit(self, ctx:FinLangParser.RateLitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#orExpr.
    def visitOrExpr(self, ctx:FinLangParser.OrExprContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#convertCall.
    def visitConvertCall(self, ctx:FinLangParser.ConvertCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#addSub.
    def visitAddSub(self, ctx:FinLangParser.AddSubContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#unary.
    def visitUnary(self, ctx:FinLangParser.UnaryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#varRef.
    def visitVarRef(self, ctx:FinLangParser.VarRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#capitalizarCall.
    def visitCapitalizarCall(self, ctx:FinLangParser.CapitalizarCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#mulDiv.
    def visitMulDiv(self, ctx:FinLangParser.MulDivContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#strLit.
    def visitStrLit(self, ctx:FinLangParser.StrLitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#cuotaCall.
    def visitCuotaCall(self, ctx:FinLangParser.CuotaCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#temCall.
    def visitTemCall(self, ctx:FinLangParser.TemCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#boolLit.
    def visitBoolLit(self, ctx:FinLangParser.BoolLitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#interesTotalCall.
    def visitInteresTotalCall(self, ctx:FinLangParser.InteresTotalCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#relational.
    def visitRelational(self, ctx:FinLangParser.RelationalContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#funcCall.
    def visitFuncCall(self, ctx:FinLangParser.FuncCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#equality.
    def visitEquality(self, ctx:FinLangParser.EqualityContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by FinLangParser#andExpr.
    def visitAndExpr(self, ctx:FinLangParser.AndExprContext):
        return self.visitChildren(ctx)



del FinLangParser