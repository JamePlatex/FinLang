"""Oráculo numérico independiente del compilador.

Calcula los mismos valores financieros que el código LLVM generado, pero con
numpy-financial (biblioteca externa) y fórmulas cerradas en Python puro, sin
usar nada de FinLang. tests/numericos.py compara ambos resultados.

Uso: python tools/oraculo.py   (imprime el ejemplo 30000 USD, TEA 12%, 36 meses)
"""
import numpy_financial as npf


def tem(tea):
    return (1 + tea) ** (1 / 12) - 1


def cuota(monto, tea, n):
    return float(-npf.pmt(tem(tea), n, monto))


def interes_total(monto, tea, n):
    return cuota(monto, tea, n) * n - monto


def cronograma(monto, tea, n, comision=0.0, seguro=0.0):
    i, r, saldo, filas = tem(tea), cuota(monto, tea, n), monto, []
    for k in range(1, n + 1):
        interes = float(-npf.ipmt(i, k, n, monto))      # interés del periodo k según numpy-financial
        amort = r - interes
        costos = comision + seguro * saldo
        filas.append((k, saldo, interes, amort, r, costos, r + costos, saldo - amort))
        saldo -= amort
    return filas


def tcea(monto, tea, n, comision=0.0, seguro=0.0):
    flujos = [monto] + [-f[6] for f in cronograma(monto, tea, n, comision, seguro)]
    return (1 + float(npf.irr(flujos))) ** 12 - 1


if __name__ == "__main__":
    m, t, n = 30000, 0.12, 36
    print(f"TEM            {tem(t) * 100:.4f}%")
    print(f"Cuota          {cuota(m, t, n):.2f} USD")
    print(f"Interés total  {interes_total(m, t, n):.2f} USD")
    print(f"TCEA           {tcea(m, t, n) * 100:.4f}%")
    print(f"Consumo 10000 PEN, 20%, 12m, comisión 10, seguro 0.08%: cuota {cuota(10000, .2, 12):.2f}, "
          f"TCEA {tcea(10000, .2, 12, 10, .0008) * 100:.4f}%")
    print(f"Capitalizar 1000 al 1% 12 meses: {1000 * 1.01 ** 12:.2f}")
    s, k = 1000.0, 0
    while s < 1100:
        s, k = s * 1.01, k + 1
    print(f"Ahorro 1%: {k} meses, {s:.2f};  375*0.2667 = {375 * 0.2667:.4f}")
    for f in cronograma(m, t, n)[:2] + cronograma(m, t, n)[-1:]:
        print("  ", " ".join(f"{x:10.2f}" for x in f))
