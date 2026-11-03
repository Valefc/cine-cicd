"""Informe educativo sobre películas (conjunto Bechdel de FiveThirtyEight).

Lee datos/movies.csv, valida los datos y genera public/index.html.
Solo usa la biblioteca estándar de Python 3.12. No descarga nada.

Uso (desde la raíz del proyecto):
    python -m unittest discover -v     # ejecuta las pruebas
    python analizar.py                 # valida el CSV y genera public/index.html

Si tu sistema usa otro comando, sustituye python por python3 o py.
Si los datos son inválidos, el programa muestra fila y columna del error,
termina con código de salida 1 y NO genera un informe nuevo.
"""

import csv
import html
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

# --- Configuración -----------------------------------------------------------
ESTUDIANTE = "TU NOMBRE COMPLETO"  # <-- CAMBIA ESTO por tu nombre

RAIZ = Path(__file__).resolve().parent
RUTA_CSV = RAIZ / "datos" / "movies.csv"
RUTA_HTML = RAIZ / "public" / "index.html"

COLUMNAS_OBLIGATORIAS = ("imdb", "title", "year", "budget", "domgross")
# Valores faltantes: vacío, NA y #N/A (este último aparece en el CSV original)
MISSING = {"", "NA", "#N/A"}

PATRON_IMDB = re.compile(r"tt[0-9]+")  # p. ej. tt1711425
ANIO_MINIMO = 1888  # primera película conocida; nada anterior es plausible
ANIO_MAXIMO = datetime.now(timezone.utc).year + 1  # permite estrenos próximos

URL_FUENTE = "https://github.com/fivethirtyeight/data/tree/master/bechdel"
URL_LICENCIA = "https://creativecommons.org/licenses/by/4.0/"
AVISO = "Copia educativa: contiene modificaciones simuladas"


class ErrorValidacion(Exception):
    """Dato inválido en el CSV, con fila (línea del archivo) y columna."""

    def __init__(self, fila, columna, mensaje):
        self.fila = fila
        self.columna = columna
        self.mensaje = mensaje
        super().__init__(f"Fila {fila}, columna '{columna}': {mensaje}")


# --- 1. Validación -----------------------------------------------------------
def _parsear_numero(texto, fila, columna):
    """Devuelve Decimal finito >= 0, o None si el valor es faltante (NA/vacío)."""
    valor = texto.strip()
    if valor in MISSING:
        return None
    try:
        numero = Decimal(valor)
    except InvalidOperation:
        raise ErrorValidacion(fila, columna, f"'{texto}' no es un número") from None
    if not numero.is_finite():
        raise ErrorValidacion(fila, columna, f"'{texto}' no es un número finito")
    if numero < 0:
        raise ErrorValidacion(fila, columna, f"valor negativo no permitido ({texto})")
    return numero


def validar_lineas(lineas):
    """Valida un CSV (iterable de líneas o archivo abierto con newline='').

    Devuelve una lista de diccionarios con imdb, title, year (int),
    budget y domgross (Decimal o None), en el orden original.
    Lanza ErrorValidacion si algo es inválido.
    """
    lector = csv.DictReader(lineas)
    cabecera = lector.fieldnames
    if not cabecera:
        raise ErrorValidacion(1, "(cabecera)", "el archivo está vacío o sin cabecera")
    for col in COLUMNAS_OBLIGATORIAS:
        if col not in cabecera:
            raise ErrorValidacion(1, col, "falta la columna obligatoria en la cabecera")

    peliculas = []
    vistos = set()
    for registro in lector:
        fila = lector.line_num  # línea del archivo donde termina el registro
        if None in registro:
            raise ErrorValidacion(fila, "(fila)", "tiene más campos que la cabecera")
        faltantes = [c for c, v in registro.items() if v is None]
        if faltantes:
            raise ErrorValidacion(fila, faltantes[0], "la fila tiene menos campos que la cabecera")

        imdb = registro["imdb"].strip()
        if not imdb:
            raise ErrorValidacion(fila, "imdb", "identificador vacío")
        if imdb in vistos:
            raise ErrorValidacion(fila, "imdb", f"identificador duplicado ({imdb})")
        if not PATRON_IMDB.fullmatch(imdb):
            raise ErrorValidacion(
                fila, "imdb", f"formato inválido '{imdb}' (debe ser 'tt' seguido de dígitos)"
            )
        vistos.add(imdb)

        titulo = html.unescape(registro["title"]).strip()
        if not titulo:
            raise ErrorValidacion(fila, "title", "título vacío")

        texto_anio = registro["year"].strip()
        if not re.fullmatch(r"[0-9]+", texto_anio) or int(texto_anio) <= 0:
            raise ErrorValidacion(fila, "year", f"'{registro['year']}' no es un entero positivo")
        if not ANIO_MINIMO <= int(texto_anio) <= ANIO_MAXIMO:
            raise ErrorValidacion(
                fila, "year", f"{texto_anio} fuera del rango permitido ({ANIO_MINIMO}-{ANIO_MAXIMO})"
            )

        peliculas.append({
            "imdb": imdb,
            "title": titulo,
            "year": int(texto_anio),
            "budget": _parsear_numero(registro["budget"], fila, "budget"),
            "domgross": _parsear_numero(registro["domgross"], fila, "domgross"),
        })

    if not peliculas:
        raise ErrorValidacion(2, "(registros)", "el CSV no contiene ningún registro")
    return peliculas


def validar_archivo(ruta):
    """Abre el CSV del repositorio y lo valida."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        return validar_lineas(f)


# --- 2. Cálculo --------------------------------------------------------------
def calcular_metricas(peliculas):
    """Calcula las cifras del informe. Los faltantes NO se tratan como cero."""
    ingresos = [p["domgross"] for p in peliculas if p["domgross"] is not None]
    presupuestos = [p["budget"] for p in peliculas if p["budget"] is not None]
    # sorted es estable: ante empates se mantiene el orden original
    top = sorted(
        (p for p in peliculas if p["domgross"] is not None),
        key=lambda p: p["domgross"],
        reverse=True,
    )[:10]
    return {
        "total": len(peliculas),
        "suma_domgross": sum(ingresos, Decimal(0)),
        "con_domgross": len(ingresos),
        "faltantes_domgross": len(peliculas) - len(ingresos),
        "media_budget": (sum(presupuestos, Decimal(0)) / len(presupuestos)) if presupuestos else None,
        "con_budget": len(presupuestos),
        "top10": top,
        "primeras10": peliculas[:10],
    }


# --- 3. Generación de HTML ---------------------------------------------------
def _e(texto):
    """Escapa texto para HTML (el título ya viene decodificado con unescape)."""
    return html.escape(str(texto), quote=True)


def _usd(valor):
    return "NA" if valor is None else f"{valor:,.0f}"


def generar_html(metricas, sha="local", fecha_utc=None):
    """Devuelve el documento HTML completo como texto."""
    if fecha_utc is None:
        fecha_utc = datetime.now(timezone.utc)
    fecha = fecha_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    media = "NA" if metricas["media_budget"] is None else f"{metricas['media_budget']:,.2f}"

    top = metricas["top10"]
    maximo = top[0]["domgross"] if top else Decimal(0)
    barras = []
    for p in top:
        pct = float(p["domgross"] / maximo * 100) if maximo > 0 else 0
        barras.append(
            f'<div class="fila-barra"><span class="etiqueta">{_e(p["title"])} ({p["year"]})</span>'
            f'<span class="pista"><span class="barra" style="width:{pct:.1f}%"></span></span>'
            f'<span class="valor">{_usd(p["domgross"])}</span></div>'
        )
    grafico = "\n".join(barras) or "<p>No hay ingresos disponibles.</p>"

    filas = "\n".join(
        f'<tr><td>{_e(p["imdb"])}</td><td>{_e(p["title"])}</td><td>{p["year"]}</td>'
        f'<td class="num">{_usd(p["budget"])}</td><td class="num">{_usd(p["domgross"])}</td></tr>'
        for p in metricas["primeras10"]
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de películas (Bechdel) - CI/CD</title>
<style>
  body {{ font-family: system-ui, Arial, sans-serif; max-width: 960px; margin: 0 auto; padding: 1.5rem; color: #1b1b1b; line-height: 1.5; }}
  h1 {{ margin-bottom: .2rem; }}
  .aviso {{ background: #fff3cd; border-left: 4px solid #e0a800; padding: .6rem 1rem; margin: 1rem 0; }}
  .tarjetas {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .8rem; margin: 1rem 0; }}
  .tarjeta {{ border: 1px solid #ccc; border-radius: 8px; padding: .8rem; }}
  .tarjeta strong {{ display: block; font-size: 1.4rem; }}
  .tarjeta small {{ color: #555; }}
  .fila-barra {{ display: grid; grid-template-columns: 220px 1fr 120px; gap: .5rem; align-items: center; margin: .25rem 0; font-size: .9rem; }}
  .pista {{ background: #eee; border-radius: 4px; height: 16px; display: block; }}
  .barra {{ background: #2b6cb0; height: 16px; border-radius: 4px; display: block; }}
  .valor {{ text-align: right; font-variant-numeric: tabular-nums; }}
  table {{ border-collapse: collapse; width: 100%; margin: .5rem 0; }}
  th, td {{ border: 1px solid #ccc; padding: .35rem .5rem; text-align: left; }}
  th {{ background: #f2f2f2; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  footer {{ margin-top: 2rem; font-size: .9rem; color: #444; border-top: 1px solid #ccc; padding-top: 1rem; }}
  @media (max-width: 640px) {{ .fila-barra {{ grid-template-columns: 1fr; }} .valor {{ text-align: left; }} }}
</style>
</head>
<body>
<h1>Informe de películas: datos Bechdel</h1>
<p>Estudiante: <strong>{_e(ESTUDIANTE)}</strong></p>
<div class="aviso"><strong>{_e(AVISO)}</strong>. Los cambios de esta práctica son simulaciones y no representan correcciones de la investigación original.</div>

<section class="tarjetas">
  <div class="tarjeta"><small>Total de películas</small><strong>{metricas['total']}</strong></div>
  <div class="tarjeta"><small>Suma de domgross disponible (USD nominales, muestra histórica)</small><strong>{_usd(metricas['suma_domgross'])}</strong></div>
  <div class="tarjeta"><small>Media del presupuesto disponible (USD nominales, {metricas['con_budget']} películas con dato)</small><strong>{media}</strong></div>
  <div class="tarjeta"><small>Películas con ingreso (domgross) faltante</small><strong>{metricas['faltantes_domgross']}</strong></div>
</section>

<p>Nota: <code>domgross</code> son ingresos de taquilla en Estados Unidos, en dólares nominales del año de estreno. Las sumas corresponden a esta muestra histórica y no son una comparación ajustada por inflación. Los faltantes (NA) no se cuentan como cero.</p>

<h2>Las diez películas con mayor domgross</h2>
<div role="img" aria-label="Gráfico de barras de las diez películas con mayor domgross">
{grafico}
</div>

<h2>Primeras diez filas del CSV (orden original)</h2>
<table>
<thead><tr><th>imdb</th><th>title</th><th>year</th><th>budget (USD)</th><th>domgross (USD)</th></tr></thead>
<tbody>
{filas}
</tbody>
</table>

<footer>
  <p>Datos: <a href="{URL_FUENTE}">FiveThirtyEight, conjunto Bechdel</a>. Licencia de datos:
  <a href="{URL_LICENCIA}">CC BY 4.0</a>. Atribución: FiveThirtyEight.</p>
  <p>{_e(AVISO)}.</p>
  <p>Generado: {_e(fecha)} | Commit: <code>{_e(sha)}</code></p>
</footer>
</body>
</html>
"""


# --- Programa principal ------------------------------------------------------
def main():
    try:
        peliculas = validar_archivo(RUTA_CSV)
    except FileNotFoundError:
        print(f"ERROR: no se encontró {RUTA_CSV}", file=sys.stderr)
        return 1
    except ErrorValidacion as error:
        print(f"ERROR de validación en {RUTA_CSV.name}: {error}", file=sys.stderr)
        return 1

    metricas = calcular_metricas(peliculas)
    sha = os.environ.get("GITHUB_SHA") or "local"
    documento = generar_html(metricas, sha=sha)

    RUTA_HTML.parent.mkdir(parents=True, exist_ok=True)
    RUTA_HTML.write_text(documento, encoding="utf-8")
    print(f"Informe generado en {RUTA_HTML} ({metricas['total']} películas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
