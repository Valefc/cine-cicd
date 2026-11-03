"""Pruebas de analizar.py con datos pequeños, independientes del CSV real.

Ejecutar:  python -m unittest discover -v
"""

import io
import unittest
from decimal import Decimal

import analizar

CABECERA = "year,imdb,title,budget,domgross,otra\n"


def csv_de(*filas, cabecera=CABECERA):
    return io.StringIO(cabecera + "".join(f + "\n" for f in filas))


class PruebasCalculo(unittest.TestCase):
    def test_suma_y_media_conocidas(self):
        datos = csv_de(
            "2000,tt1,A,100,1000,x",
            "2001,tt2,B,300,2000,x",
            "2002,tt3,C,200,3000,x",
        )
        m = analizar.calcular_metricas(analizar.validar_lineas(datos))
        self.assertEqual(m["total"], 3)
        self.assertEqual(m["suma_domgross"], Decimal(6000))
        self.assertEqual(m["media_budget"], Decimal(200))
        self.assertEqual(m["faltantes_domgross"], 0)

    def test_na_no_se_convierte_en_cero(self):
        datos = csv_de(
            "2000,tt1,A,100,1000,x",
            "2001,tt2,B,NA,NA,x",
            "2002,tt3,C,300,,x",
            "2003,tt4,D,#N/A,#N/A,x",
        )
        pelis = analizar.validar_lineas(datos)
        self.assertIsNone(pelis[1]["domgross"])
        self.assertIsNone(pelis[2]["domgross"])
        self.assertIsNone(pelis[3]["domgross"])  # #N/A del CSV original
        m = analizar.calcular_metricas(pelis)
        self.assertEqual(m["suma_domgross"], Decimal(1000))
        self.assertEqual(m["faltantes_domgross"], 3)
        # Media sobre los 2 presupuestos disponibles, no sobre 3 (NA != 0)
        self.assertEqual(m["media_budget"], Decimal(200))
        self.assertEqual(m["con_budget"], 2)

    def test_top10_y_primeras10_en_orden(self):
        filas = [f"2000,tt{i},P{i},10,{i * 10},x" for i in range(1, 13)]
        m = analizar.calcular_metricas(analizar.validar_lineas(csv_de(*filas)))
        self.assertEqual(len(m["top10"]), 10)
        self.assertEqual(m["top10"][0]["imdb"], "tt12")
        self.assertEqual([p["imdb"] for p in m["primeras10"]][:3], ["tt1", "tt2", "tt3"])


class PruebasValidacion(unittest.TestCase):
    def assertRechaza(self, datos, columna):
        with self.assertRaises(analizar.ErrorValidacion) as ctx:
            analizar.validar_lineas(datos)
        self.assertEqual(ctx.exception.columna, columna)
        return ctx.exception

    def test_rechaza_domgross_negativo(self):
        error = self.assertRechaza(csv_de("2000,tt1,A,100,-100,x"), "domgross")
        self.assertEqual(error.fila, 2)

    def test_rechaza_columna_obligatoria_ausente(self):
        datos = csv_de("2000,tt1,A,100,x", cabecera="year,imdb,title,budget,otra\n")
        self.assertRechaza(datos, "domgross")

    def test_rechaza_valores_no_numericos_o_no_finitos(self):
        self.assertRechaza(csv_de("2000,tt1,A,abc,10,x"), "budget")
        self.assertRechaza(csv_de("2000,tt1,A,100,nan,x"), "domgross")
        self.assertRechaza(csv_de("2000,tt1,A,inf,10,x"), "budget")

    def test_rechaza_imdb_duplicado_o_vacio(self):
        self.assertRechaza(csv_de("2000,tt1,A,1,1,x", "2001,tt1,B,1,1,x"), "imdb")
        self.assertRechaza(csv_de("2000,,A,1,1,x"), "imdb")

    def test_rechaza_titulo_vacio_y_year_invalido(self):
        self.assertRechaza(csv_de("2000,tt1,,1,1,x"), "title")
        self.assertRechaza(csv_de("abcd,tt1,A,1,1,x"), "year")
        self.assertRechaza(csv_de("0,tt1,A,1,1,x"), "year")
        self.assertRechaza(csv_de("-5,tt1,A,1,1,x"), "year")

    def test_rechaza_numero_incorrecto_de_campos(self):
        self.assertRechaza(csv_de("2000,tt1,A,1"), "domgross")  # faltan campos
        self.assertRechaza(csv_de("2000,tt1,A,1,1,x,extra"), "(fila)")  # sobran

    def test_rechaza_csv_sin_registros(self):
        self.assertRechaza(csv_de(), "(registros)")


class PruebasHtml(unittest.TestCase):
    def test_entidades_y_escape(self):
        datos = csv_de(
            "2013,tt1,21 &amp; Over,1,1,x",
            '2014,tt2,"<script>alert(1)</script>",1,1,x',
        )
        m = analizar.calcular_metricas(analizar.validar_lineas(datos))
        pagina = analizar.generar_html(m, sha="abc123")
        self.assertIn("21 &amp; Over", pagina)  # decodificado y vuelto a escapar
        self.assertNotIn("&amp;amp;", pagina)
        self.assertNotIn("<script>alert", pagina)
        self.assertIn("&lt;script&gt;", pagina)
        self.assertIn("abc123", pagina)
        self.assertIn("CC BY 4.0", pagina)
        self.assertIn("Copia educativa: contiene modificaciones simuladas", pagina)


if __name__ == "__main__":
    unittest.main()
