#Versión documentada
from hashi_solver import HashiSolver

# Texto de ayuda para el modo humano
HELP = """\
Comandos disponibles (modo humano):
  LOAD <ruta>                 Carga un tablero desde archivo
  SHOW                        Muestra el tablero con puentes
  ADD r1 c1 r2 c2 k           Agrega k∈{1,2} puentes entre (r1,c1) y (r2,c2)  [1-based]
  REM r1 c1 r2 c2 k           Quita k∈{1,2} puentes entre (r1,c1) y (r2,c2)
  CHECK                       Valida reglas (cuentas por isla + conectividad)
  PENDING                     Muestra cuántos puentes faltan por isla
  HELP                        Muestra esta ayuda
  EXIT                        Sale del programa
"""

def to0(r, c):
    """
    Convierte coordenadas 1-based (las que ingresa el usuario) a 0-based
    (las que usa internamente Board).
    """
    return (r - 1, c - 1)

def main():
    print("=== Hashiwokakero (Consola) ===")
    solver = HashiSolver()
    board = None

    # ------------------------------------------------------------------
    # 1) Cargar tablero inicial
    # ------------------------------------------------------------------
    while board is None:
        try:
            path = input("Ruta del archivo de tablero (ENTER para salir): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós!")
            return

        if not path:
            print("No se cargó ningún tablero. Saliendo.")
            return

        try:
            board = solver.load_board(path)
            print(f"Tablero {board.n_rows}x{board.n_cols} cargado.\n")
            solver.print_board(board)
        except Exception as e:
            print(f"Error cargando tablero: {e}")
            board = None  # volver a pedir

    # ------------------------------------------------------------------
    # 2) Elegir tipo de jugador: Humano o Sintético
    # ------------------------------------------------------------------
    while True:
        try:
            modo = input("\n¿Quién jugará? [H]umano / [S]intético: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós!")
            return
        if modo in ("H", "S"):
            break
        print("Opción no válida. Responde con H o S.")

    # ------------------------------------------------------------------
    # 2.a) Modo sintético: el algoritmo intenta resolver de una vez y salimos
    # ------------------------------------------------------------------
    if modo == "S":
        print("\n=== Modo jugador sintético (BT + Forward Checking + MRV) ===")
        exito = solver.solve_csp(board, verbose=False)
        if exito:
            print("\nSolución encontrada por el jugador sintético:\n")
            solver.print_board(board)
            ok, msg = board.full_check()
            print("\nCHECK final:", "OK" if ok else f"INVALIDO: {msg}")
        else:
            print("\nNo se encontró solución. "
                  "Verifica que el tablero sea resoluble y respete el enunciado.")
        # Importante: salimos después de que juegue el sintético
        return

    # ------------------------------------------------------------------
    # 2.b) Modo humano: bucle de comandos
    # ------------------------------------------------------------------
    print("\nModo humano. Escribe HELP para ver comandos.\n")

    while True:
        try:
            raw = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].upper()

        try:
            # ----------------------------------------------------------
            # HELP: mostrar ayuda
            # ----------------------------------------------------------
            if cmd == "HELP":
                print(HELP)

            # ----------------------------------------------------------
            # LOAD <ruta>: cargar otro tablero desde archivo
            # ----------------------------------------------------------
            elif cmd == "LOAD":
                if len(parts) != 2:
                    print("Uso: LOAD <ruta>")
                    continue
                path = parts[1]
                try:
                    board = solver.load_board(path)
                    print(f"Tablero {board.n_rows}x{board.n_cols} cargado.")
                    solver.print_board(board)
                except Exception as e:
                    print(f"Error cargando tablero: {e}")
                    board = None

            # ----------------------------------------------------------
            # SHOW: mostrar el tablero actual con puentes
            # ----------------------------------------------------------
            elif cmd == "SHOW":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                solver.print_board(board)

            # ----------------------------------------------------------
            # ADD r1 c1 r2 c2 k: agregar k puentes entre dos islas (1-based)
            # ----------------------------------------------------------
            elif cmd == "ADD":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                if len(parts) != 6:
                    print("Uso: ADD r1 c1 r2 c2 k   (1-based)")
                    continue
                r1, c1, r2, c2, k = map(int, parts[1:])
                a = to0(r1, c1)
                b = to0(r2, c2)
                ok, msg = board.add_bridge(a, b, k)
                print(msg)
                if ok:
                    solver.print_board(board)

            # ----------------------------------------------------------
            # REM r1 c1 r2 c2 k: quitar k puentes entre dos islas (1-based)
            # ----------------------------------------------------------
            elif cmd == "REM":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                if len(parts) != 6:
                    print("Uso: REM r1 c1 r2 c2 k   (1-based)")
                    continue
                r1, c1, r2, c2, k = map(int, parts[1:])
                a = to0(r1, c1)
                b = to0(r2, c2)
                ok, msg = board.remove_bridge(a, b, k)
                print(msg)
                if ok:
                    solver.print_board(board)

            # ----------------------------------------------------------
            # CHECK: validar reglas finales (cuentas + conectividad)
            # ----------------------------------------------------------
            elif cmd == "CHECK":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                ok, msg = board.full_check()
                print("OK" if ok else f"INVALIDO: {msg}")

            # ----------------------------------------------------------
            # PENDING: ver cuántos puentes faltan por isla
            # ----------------------------------------------------------
            elif cmd == "PENDING":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                out = []
                for (r, c, val) in board.islands:
                    pend = board.pending((r, c))
                    out.append(f"({r+1},{c+1})={val} -> faltan {pend}")
                print(", ".join(out) if out else "(sin islas)")

            # ----------------------------------------------------------
            # EXIT: salir del programa
            # ----------------------------------------------------------
            elif cmd == "EXIT":
                print("Adiós!")
                break

            # ----------------------------------------------------------
            # Comando desconocido
            # ----------------------------------------------------------
            else:
                print("Comando no reconocido. Escribe HELP.")

        except Exception as e:
            # Cualquier excepción inesperada se muestra pero no tumba el programa
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
