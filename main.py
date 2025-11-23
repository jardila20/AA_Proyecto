from hashi_solver import HashiSolver

HELP = """\
Comandos disponibles:
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
    return (r-1, c-1)

def main():
    print("=== Hashiwokakero (Consola) ===")
    print("Escribe HELP para ver comandos.\n")
    solver = HashiSolver()
    board = None

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
            if cmd == "HELP":
                print(HELP)

            elif cmd == "LOAD":
                if len(parts) != 2:
                    print("Uso: LOAD <ruta>")
                    continue
                path = parts[1]
                board = solver.load_board(path)
                print(f"Tablero {board.n_rows}x{board.n_cols} cargado.")
                solver.print_board(board)

            elif cmd == "SHOW":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                solver.print_board(board)

            elif cmd == "ADD":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                if len(parts) != 6:
                    print("Uso: ADD r1 c1 r2 c2 k   (1-based)")
                    continue
                r1, c1, r2, c2, k = map(int, parts[1:])
                a = to0(r1, c1); b = to0(r2, c2)
                ok, msg = board.add_bridge(a, b, k)
                print(msg)
                if ok:
                    solver.print_board(board)

            elif cmd == "REM":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                if len(parts) != 6:
                    print("Uso: REM r1 c1 r2 c2 k   (1-based)")
                    continue
                r1, c1, r2, c2, k = map(int, parts[1:])
                a = to0(r1, c1); b = to0(r2, c2)
                ok, msg = board.remove_bridge(a, b, k)
                print(msg)
                if ok:
                    solver.print_board(board)

            elif cmd == "CHECK":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                ok, msg = board.full_check()
                print("OK" if ok else f"INVALIDO: {msg}")

            elif cmd == "PENDING":
                if not board:
                    print("Primero LOAD <ruta>.")
                    continue
                out = []
                for (r,c,val) in board.islands:
                    pend = board.pending((r,c))
                    out.append(f"({r+1},{c+1})={val} -> faltan {pend}")
                print(", ".join(out) if out else "(sin islas)")

            elif cmd == "EXIT":
                print("Adiós!")
                break

            else:
                print("Comando no reconocido. Escribe HELP.")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
