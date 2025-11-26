from board import Board

class HashiSolver:
    """
    Carga tableros y ofrece un solver sintético basado en:
    - Backtracking
    - Forward checking sobre las cuentas de cada isla
    - Heurística MRV (Minimum Remaining Values) sobre las aristas (posibles puentes)
    """

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Utilidades básicas
    # ------------------------------------------------------------------
    def load_board(self, path: str) -> Board:
        """Lee un archivo de texto y construye un Board."""
        with open(path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        return Board.parse_from_lines(lines)

    def print_board(self, board: Board) -> None:
        """Imprime el tablero en ASCII."""
        print(board.render())

    # ------------------------------------------------------------------
    # Construcción del grafo de variables (posibles puentes)
    # ------------------------------------------------------------------
    def _build_edges(self, board: Board):
        """
        Construye la lista de aristas posibles (variables del CSP).

        Cada arista corresponde a dos islas que se ven en línea recta
        (vecinos visibles U,D,L,R). Para cada isla (r,c) se guarda además
        la lista de índices de aristas incidentes.
        """
        edges = []  # lista de pares ((r1,c1), (r2,c2))
        seen = set()

        for (r, c, _) in board.islands:
            a = (r, c)
            vis = board.visible_neighbors.get((r, c), {})
            for d in ("U", "D", "L", "R"):
                b = vis.get(d)
                if b is None:
                    continue
                key = frozenset({a, b})
                if key not in seen:
                    seen.add(key)
                    edges.append((a, b))

        # mapa isla -> índices de aristas incidentes
        incident = {(r, c): [] for (r, c, _) in board.islands}
        for idx, (a, b) in enumerate(edges):
            incident[a].append(idx)
            incident[b].append(idx)

        return edges, incident

    # ------------------------------------------------------------------
    # Solver sintético: BT + Forward Checking + MRV
    # ------------------------------------------------------------------
    def solve_csp(self, board: Board, verbose: bool = False, use_mrv: bool = True) -> bool:
        """
        Intenta resolver el tablero partiendo del estado actual de `board`.

        IMPORTANTE: el uso esperado es arrancar desde un tablero sin puentes
        (tal como está al cargarlo desde archivo). Modifica `board` in-place.

        Devuelve:
            True  si encontró una solución que cumple:
                  - número de cada isla
                  - conectividad (un único componente)
                  - reglas de Hashi (sin cruces, máx 2 por par)
            False si no existe solución compatible con el estado actual.
        """
        # Construir variables (aristas)
        edges, incident = self._build_edges(board)
        n_edges = len(edges)

        # Dominios iniciales: cada arista puede acabar con 0,1,2 puentes
        domains = {i: {0, 1, 2} for i in range(n_edges)}
        # Conjunto de variables aún sin fijar
        unassigned = set(range(n_edges))

        # ---------------- Forward Checking + pequeña propagación ----------------
        def propagate(domains, unassigned) -> bool:
            """
            Aplica forward checking básico sobre las cuentas de cada isla.

            Para cada isla i:
                used   = grado ya fijo en el board (puentes ya añadidos)
                left   = objetivo - used
                U      = aristas aún no asignadas incidentes a i
                mins   = suma de los mínimos de dominio de aristas de U
                maxs   = suma de los máximos de dominio de aristas de U

            Se exige que:
                left >= mins  y  left <= maxs

            Además se aplican reglas simples de propagación:
                - left == 0     -> todas las aristas de U forzadas a 0
                - left == 2*|U| -> todas forzadas a 2
                - left == 1 y |U| == 1 -> esa única arista forzada a 1
            """
            changed = True
            while changed:
                changed = False
                for (r, c, objetivo) in board.islands:
                    pos = (r, c)
                    used = board.degree(pos)
                    left = objetivo - used
                    if left < 0:
                        return False

                    # aristas incidentes que aún no están fijadas
                    u_edges = [e for e in incident[pos] if e in unassigned]

                    # si no hay aristas libres, la isla ya debe estar completa
                    if not u_edges:
                        if left != 0:
                            return False
                        continue

                    mins = 0
                    maxs = 0
                    for e in u_edges:
                        d = domains[e]
                        if not d:
                            return False
                        mins += min(d)
                        maxs += max(d)

                    # chequeo de viabilidad
                    if left < mins or left > maxs:
                        return False

                    # reglas simples de forzado
                    d = len(u_edges)
                    if left == 0:
                        # todas deben quedar en 0
                        for e in u_edges:
                            if domains[e] != {0}:
                                domains[e] = {0}
                                changed = True
                    elif left == 2 * d:
                        # todas deben ser 2
                        for e in u_edges:
                            if domains[e] != {2}:
                                domains[e] = {2}
                                changed = True
                    elif left == 1 and d == 1:
                        # única arista debe ser 1
                        e = u_edges[0]
                        if domains[e] != {1}:
                            domains[e] = {1}
                            changed = True

            return True

        # Propagación inicial (por si el tablero ya es obviamente inválido)
        if not propagate(domains, unassigned):
            return False

        # ---------------- Backtracking con MRV ----------------
        def backtrack(domains, unassigned) -> bool:
            # Caso base: todas las aristas tienen valor
            if not unassigned:
                ok, _ = board.full_check()
                if verbose:
                    print("CHECK final:", "OK" if ok else "INVALIDO")
                return ok

            # Seleccionar variable (arista) siguiente: MRV o primera que salga
            if use_mrv:
                var = min(unassigned, key=lambda i: len(domains[i]))
            else:
                var = next(iter(unassigned))

            a, b = edges[var]

            # Probar valores del dominio (2,1,0 suele podar más rápido)
            for val in sorted(domains[var], reverse=True):
                # multiplicidad actual en el board para esta arista
                key = frozenset({a, b})
                info = board.bridges.get(key)
                k_current = info["k"] if info else 0

                # Trabajamos con "valor final": no podemos disminuir, solo aumentar
                if val < k_current:
                    continue

                delta = val - k_current

                # Aplicar el cambio sobre el board
                if delta > 0:
                    ok, _ = board.add_bridge(a, b, delta)
                    if not ok:
                        # No se puede llegar a ese valor (cruce, exceso, etc.)
                        continue

                # Clonar dominos y conjunto de no asignadas para esta rama
                new_domains = {i: set(vs) for i, vs in domains.items()}
                new_unassigned = set(unassigned)

                # Fijar la variable actual
                new_domains[var] = {val}
                new_unassigned.remove(var)

                # Forward checking / propagación
                if not propagate(new_domains, new_unassigned):
                    # Deshacer y probar siguiente valor
                    if delta > 0:
                        board.remove_bridge(a, b, delta)
                    continue

                if verbose:
                    print(f"[BT] Arista {var} {a} - {b} = {val}")

                # Recursión
                if backtrack(new_domains, new_unassigned):
                    return True

                # Deshacer el cambio en el board antes de probar el siguiente valor
                if delta > 0:
                    board.remove_bridge(a, b, delta)

            # Ningún valor llevó a solución
            return False

        return backtrack(domains, unassigned)
    


        # ------------------------------------------------------------------
    # Dibujo gráfico de la solución con matplotlib
    # ------------------------------------------------------------------
    def save_solution_image(self, board: Board, filename: str = "solucion_hashi.png") -> None:
        """
        Genera una imagen PNG del tablero actual usando matplotlib.

        - Dibuja una grilla punteada.
        - Las islas como círculos blancos con borde negro y número dentro.
        - Los puentes como líneas simples o dobles, horizontales o verticales.

        Requiere tener instalado matplotlib:
            pip install matplotlib
        """
        import matplotlib.pyplot as plt

        # Pequeño helper: convertir (fila,columna) 0-based a coordenadas (x,y)
        # en el plano de dibujo. Usamos +0.5 para centrar cada isla en la celda,
        # y "invertimos" la fila para que la fila 0 quede arriba en la imagen,
        # como en el enunciado.
        def cell_to_xy(r: int, c: int):
            x = c + 0.5
            y = (board.n_rows - 1 - r) + 0.5
            return x, y

        fig, ax = plt.subplots(figsize=(4, 4))
        ax.set_aspect("equal")

        # ------------------- grilla punteada -------------------
        for x in range(board.n_cols + 1):
            ax.axvline(x, linestyle=":", linewidth=0.5, color="lightgray")
        for y in range(board.n_rows + 1):
            ax.axhline(y, linestyle=":", linewidth=0.5, color="lightgray")

        # ------------------- puentes -------------------
        for key, info in board.bridges.items():
            if info["k"] <= 0:
                continue

            a, b = list(key)
            (r1, c1) = a
            (r2, c2) = b
            x1, y1 = cell_to_xy(r1, c1)
            x2, y2 = cell_to_xy(r2, c2)
            k = info["k"]

            # Puentes horizontales o verticales (caso estándar Hashi)
            if info["dir"] == board.H:  # horizontal
                if k == 1:
                    ax.plot([x1, x2], [y1, y2], linewidth=2, color="black")
                else:
                    # doble: dos líneas paralelas, una un poco arriba y otra abajo
                    offset = 0.10
                    ax.plot([x1, x2], [y1 + offset, y2 + offset], linewidth=2, color="black")
                    ax.plot([x1, x2], [y1 - offset, y2 - offset], linewidth=2, color="black")

            elif info["dir"] == board.V:  # vertical
                if k == 1:
                    ax.plot([x1, x2], [y1, y2], linewidth=2, color="black")
                else:
                    # doble: dos líneas paralelas, una a la izquierda y otra a la derecha
                    offset = 0.10
                    ax.plot([x1 + offset, x2 + offset], [y1, y2], linewidth=2, color="black")
                    ax.plot([x1 - offset, x2 - offset], [y1, y2], linewidth=2, color="black")

            else:
                # Si en algún momento habilitas diagonales y quieres dibujarlas,
                # puedes tratarlas aquí. Ahora simplemente las dibujamos como una
                # sola línea.
                if k == 1:
                    ax.plot([x1, x2], [y1, y2], linewidth=2, color="black")
                else:
                    offset = 0.10
                    ax.plot([x1, x2], [y1, y2], linewidth=2, color="black")
                    ax.plot([x1 + offset, x2 + offset], [y1 + offset, y2 + offset],
                            linewidth=2, color="black")

        # ------------------- islas -------------------
        for (r, c, val) in board.islands:
            x, y = cell_to_xy(r, c)
            # círculo blanco con borde negro
            circle = plt.Circle((x, y), 0.35, edgecolor="black",
                                facecolor="white", linewidth=2)
            ax.add_patch(circle)
            # número centrado
            ax.text(x, y, str(val), ha="center", va="center",
                    fontsize=14, fontweight="bold", color="black")

        # Ajustar límites y quitar ejes
                # Ajustar límites y quitar ejes
        ax.set_xlim(0, board.n_cols)
        ax.set_ylim(0, board.n_rows)
        # ax.invert_yaxis()  # NO la necesitamos porque ya volteamos y en cell_to_xy
        ax.axis("off")
        plt.tight_layout()

        fig.savefig(filename, dpi=200)
        plt.close(fig)


