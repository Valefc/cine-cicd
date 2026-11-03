"""Atajo para publicar: prueba, valida, hace commit y push en un solo comando.

Uso (desde la raíz del proyecto):
    python publicar.py "Simular aumento de taquilla de USD 1000000"
    python publicar.py                      # usa un mensaje automático con la fecha
    python publicar.py "Prueba controlada: taquilla inválida" --forzar

Pasos:
  1. python -m unittest discover
  2. python analizar.py          (valida el CSV y genera public/index.html)
  3. git add -A, git commit, git push origin main
  4. GitHub Actions hace el resto: verificar -> publicar.

Si las pruebas o la validación fallan en tu computadora, NO se hace commit.
Con --forzar se omiten esos controles locales y se sube igual; sirve para la
demostración del paso 8 (dato inválido), donde el bloqueo debe ocurrir en Actions.
"""

import subprocess
import sys
from datetime import datetime

RAMA = "main"


def ejecutar(comando, titulo):
    print(f"\n==> {titulo}")
    return subprocess.run(comando).returncode == 0


def salida(comando):
    r = subprocess.run(comando, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def main(argumentos):
    forzar = "--forzar" in argumentos
    textos = [a for a in argumentos if a != "--forzar"]
    mensaje = " ".join(textos).strip() or f"Actualización {datetime.now():%Y-%m-%d %H:%M}"

    if subprocess.run(["git", "--version"], capture_output=True).returncode != 0:
        print("ERROR: git no está instalado o no está en el PATH.", file=sys.stderr)
        return 1

    if not forzar:
        if not ejecutar([sys.executable, "-m", "unittest", "discover"], "Pruebas unitarias"):
            print("\nLas pruebas fallaron. No se hizo commit.", file=sys.stderr)
            return 1
        if not ejecutar([sys.executable, "analizar.py"], "Validar CSV y generar informe"):
            print("\nEl CSV es inválido. No se hizo commit (usa --forzar para la prueba controlada).",
                  file=sys.stderr)
            return 1
    else:
        print("Modo --forzar: se omiten los controles locales.")

    if not ejecutar(["git", "add", "-A"], "git add"):
        return 1
    _, cambios = salida(["git", "status", "--porcelain"])
    if cambios:
        if not ejecutar(["git", "commit", "-m", mensaje], f"git commit: {mensaje}"):
            return 1
    else:
        print("\nNo hay cambios nuevos para commit; se intentará el push de todos modos.")

    if not ejecutar(["git", "push", "origin", RAMA], f"git push origin {RAMA}"):
        print("\nEl push falló. Revisa tu conexión o inicia sesión en GitHub.", file=sys.stderr)
        return 1

    print("\nListo. Revisa la pestaña Actions de tu repositorio: verificar y publicar deben ir en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
