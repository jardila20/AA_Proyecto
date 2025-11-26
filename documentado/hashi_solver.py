#Versión documentada
from board import Board

class HashiSolver:
    """
    Clase encargada de:
    - Cargar un tablero desde archivo y construir un Board.
    - Imprimir el tablero en formato ASCII.
    - Implementar un "jugador sintético" que intenta resolver el puzzle.

    El jugador sintético está implementado como un CSP (problema de satisfacción
    de restricciones) con:
        * Variables: aristas posibles entre islas visibles (potenciales puentes).
        * Dominios: para cada arista, cuántos puentes puede tener al final {0,1,2}.
        * Restricciones:
            - Suma de puentes incidentes a cada isla == valor de la isla.
            - Máximo 2 puentes entre cada par de islas (Board.add_bridge lo garantiza).
            - No cruzar puentes (Board.add_bridge lo chequea).
            - Conectividad en un solo componente (Board.full_check al final).

    Técnicas usadas:
        - Backtracking (búsqueda en profundidad con retroceso).
        - Forward Checking (comprobación anticipada de inconsistencia).
        - Heurística MRV (Minimum Remaining Values) para elegir la siguiente variable.
    """

    def __init__(self):
        # En este caso no necesitamos estado interno complejo.
        # Se deja el constructor vacío por si en el futuro quieres añadir cosas.
        pass

    # ------------------------------------------------------------------
    # Utilidades básicas: cargar tablero e imprimirlo
    # ------------------------------------------------------------------
    def load_board(self, path: str) -> Board:
        """
        Carga un tablero desde un archivo de texto.

        Formato esperado:
            - Primera línea: "filas,columnas"
            - Luego 'filas' líneas con exactamente 'columnas' caracteres '0'..'8'.
        """
        with open(path, "r") as f:
            # strip() elimina saltos de línea / espacios.
            # Filtramos líneas vacías.
            lines = [line.strip() for line in f.readlines() if line.strip()]

        # Delegamos el parseo y validación a Board.parse_from_lines
        return Board.parse_from_lines(lines)

    def print_board(self, board: Board) -> None:
        """
        Pide al Board una representación ASCII del tablero actual
        (islas + puentes) y la imprime por pantalla.
        """
        print(board.render())

    # ------------------------------------------------------------------
    # Construcción del grafo de variables (aristas posibles)
    # ------------------------------------------------------------------
    def _build_edges(self, board: Board):
        """
        Construye la estructura que usaremos en el solver CSP.

        Queremos obtener:
        - edges: lista de aristas posibles. Cada arista es un par ((r1,c1), (r2,c2))
          donde ambas son islas que se ven en línea recta (U,D,L,R).
        - incident: diccionario que, para cada isla (r,c), nos da la lista de
          índices de edges que "tocan" a esa isla (es decir, las aristas incidentes).

        Esto nos permite:
          - Iterar sobre todas las variables del problema (edges).
          - Saber rápidamente qué variables afectan a la suma de una isla (incident).
        """
        edges = []      # lista de aristas ((r1,c1), (r2,c2))
        seen = set()    # para no duplicar aristas (a,b) y (b,a)

        # Recorremos todas las islas del tablero
        for (r, c, _) in board.islands:
            a = (r, c)
            # board.visible_neighbors[(r,c)] nos dice qué islas se ven en las
            # 4 direcciones: "U", "D", "L", "R"
            vis = board.visible_neighbors.get((r, c), {})
            for d in ("U", "D", "L", "R"):
                b = vis.get(d)
                if b is None:
                    continue

                # Usamos frozenset({a,b}) para no contar dos veces la misma arista
                # (a,b) y (b,a) son el mismo par de islas.
                key = frozenset({a, b})
                if key not in seen:
                    seen.add(key)
                    edges.append((a, b))

        # Ahora construimos "incident":
        # Para cada isla (r,c), guardaremos qué índices de edges la tienen como extremo.
        incident = {(r, c): [] for (r, c, _) in board.islands}
        for idx, (a, b) in enumerate(edges):
            incident[a].append(idx)
            incident[b].append(idx)

        return edges, incident

    # ------------------------------------------------------------------
    # Solver sintético: Backtracking + Forward Checking + MRV
    # ------------------------------------------------------------------
    def solve_csp(self, board: Board, verbose: bool = False, use_mrv: bool = True) -> bool:
        """
        Intenta resolver el tablero de Hashiwokakero partiendo del estado actual
        de `board`.

        Uso típico:
            - Llamar justo después de cargar un tablero (sin puentes).
            - El solver irá añadiendo puentes sobre el mismo `board` (in-place).

        Retorna:
            - True  si encontró una configuración de puentes que:
                * Hace que cada isla cumpla exactamente su número.
                * No viola las reglas (cruces, máximo 2 por par, etc.).
                * Deja el grafo en un único componente conexo.
            - False si no existe solución compatible con el estado actual del `board`.
        """

        # --------------------------------------------------------------
        # 1) Construir las "variables" del CSP = aristas (posibles puentes)
        # --------------------------------------------------------------
        edges, incident = self._build_edges(board)
        n_edges = len(edges)

        # "domains" es un diccionario:
        #   clave:   índice de arista (0..n_edges-1)
        #   valor:   conjunto de posibles multiplicidades finales {0,1,2}
        #
        # Ej: domains[5] = {0,2} significa:
        #    - la arista 5 al final sólo puede tener 0 o 2 puentes.
        domains = {i: {0, 1, 2} for i in range(n_edges)}

        # "unassigned" es el conjunto de índices de aristas que aún no hemos
        # fijado a un valor concreto (como variable libre en backtracking).
        unassigned = set(range(n_edges))

        # --------------------------------------------------------------
        # 2) Forward Checking + propagación de restricciones
        # --------------------------------------------------------------
        def propagate(domains, unassigned) -> bool:
            """
            Aplica **Forward Checking** y reglas de propagación muy simples.

            Para cada isla i con valor "objetivo", miramos:
                used = grado actual de la isla (suma de puentes ya puestos
                       en el Board).
                left = objetivo - used (cuántos puentes faltan por "recibir").
                U    = conjunto de aristas incidentes a esa isla que
                       todavía están sin asignar.

            Para esas aristas U:
                - Cada arista e tiene dominio domains[e].
                - El mínimo aporte posible de e a la isla es min(domains[e])
                - El máximo aporte posible de e a la isla es max(domains[e])

            Sumando sobre U:
                mins = sum( min(domains[e]) )
                maxs = sum( max(domains[e]) )

            Debe cumplirse:
                left >= mins   (no podemos forzar más de lo que falta)
                left <= maxs   (con las capacidades máximas alcanza)

            Si eso no se cumple -> inconsistencia -> se retorna False.

            Además, aplicamos algunas reglas de propagación:
                - Si left == 0:
                    Todas las aristas de U deben acabar en valor 0.
                - Si left == 2 * |U|:
                    Todas las aristas de U deben acabar en valor 2.
                - Si left == 1 y |U| == 1:
                    Esa arista única se fuerza a 1.

            Cada vez que modificamos algún dominio, marcamos "changed = True"
            para volver a revisar, porque esos cambios pueden producir más
            restricciones en otras islas (propagación).
            """
            changed = True

            # Repetimos mientras haya cambios en los dominios
            while changed:
                changed = False

                # Revisamos todas las islas del tablero
                for (r, c, objetivo) in board.islands:
                    pos = (r, c)
                    # "used" = cuántos puentes ya tiene esta isla en el Board
                    used = board.degree(pos)
                    # "left" = cuántos faltan para llegar al número de la isla
                    left = objetivo - used

                    # Si left < 0, ya nos pasamos del número de la isla -> inconsistente
                    if left < 0:
                        return False

                    # u_edges: aristas incidentes a esta isla que aún
                    # no han sido asignadas (están en unassigned)
                    u_edges = [e for e in incident[pos] if e in unassigned]

                    # Si no quedan aristas libres para tocar esta isla, entonces
                    # sólo es válida si left == 0 (ya está completa)
                    if not u_edges:
                        if left != 0:
                            # no hay forma de completar esta isla -> inconsistencia
                            return False
                        continue  # isla OK, seguimos

                    # Calculamos mins y maxs: mínimo y máximo total que
                    # podemos todavía aportar con estas aristas libres.
                    mins = 0
                    maxs = 0
                    for e in u_edges:
                        d = domains[e]
                        # Si alguna arista tiene dominio vacío, ya es inconsistente.
                        if not d:
                            return False
                        mins += min(d)
                        maxs += max(d)

                    # Forward checking duro: si left está fuera de [mins, maxs],
                    # este estado de dominios ya no puede llevar a solución.
                    if left < mins or left > maxs:
                        return False

                    # A partir de aquí, left está dentro de [mins, maxs],
                    # pero podemos detectar casos donde se fuerzan valores.

                    d = len(u_edges)  # número de aristas incidentes libres

                    # Caso 1: left == 0, ya no necesitamos más puentes aquí.
                    # -> Todas las aristas incidentes restantes deben contribuir 0.
                    if left == 0:
                        for e in u_edges:
                            if domains[e] != {0}:
                                domains[e] = {0}
                                changed = True

                    # Caso 2: left == 2 * d, significa que cada arista restante
                    # debe aportar el máximo posible (2 puentes) para llegar al objetivo.
                    elif left == 2 * d:
                        for e in u_edges:
                            if domains[e] != {2}:
                                domains[e] = {2}
                                changed = True

                    # Caso 3: left == 1 y sólo hay 1 arista libre.
                    # Esa arista debe tener multiplicidad 1.
                    elif left == 1 and d == 1:
                        e = u_edges[0]
                        if domains[e] != {1}:
                            domains[e] = {1}
                            changed = True

            # Si terminamos la iteración sin inconsistencias -> True
            return True

        # Propagación inicial por si el tablero ya es obviamente imposible
        if not propagate(domains, unassigned):
            return False

        # --------------------------------------------------------------
        # 3) Backtracking con MRV
        # --------------------------------------------------------------
        def backtrack(domains, unassigned) -> bool:
            """
            Función recursiva de backtracking.

            - domains:  diccionario de dominios actuales por variable.
            - unassigned: conjunto de índices de aristas aún sin fijar.

            Estrategia:
            ----------
            1. Caso base: si unassigned está vacío, ya asignamos un valor final
               a todas las aristas. En ese momento llamamos a board.full_check()
               para:
                   - verificar que cada isla cumple su número,
                   - verificar conectividad en un solo componente.
            2. Paso recursivo:
               a) Elegir una variable (arista) de unassigned.
                  Usando MRV -> la de menor tamaño de dominio.
               b) Recorrer los valores posibles de su dominio.
                     i. Aplicar ese valor al Board (add_bridge).
                    ii. Clonar domains y unassigned para la rama.
                   iii. Fijar el dominio de la variable sólo a ese valor.
                    iv. Llamar a propagate() (Forward Checking).
                     v. Si sigue siendo consistente, recursión.
                    vi. Si no, deshacer cambios y probar otro valor.
            """
            # --------- CASO BASE ---------
            if not unassigned:
                # Ya asignamos todas las variables.
                # Verificamos las condiciones finales con Board.full_check().
                ok, _ = board.full_check()
                if verbose:
                    print("CHECK final:", "OK" if ok else "INVALIDO")
                return ok

            # --------- ELECCIÓN DE VARIABLE (MRV) ---------
            if use_mrv:
                # MRV (Minimum Remaining Values):
                # Escogemos la variable con menor cantidad de valores posibles
                # en su dominio. Esto tiende a detectar conflictos antes.
                var = min(unassigned, key=lambda i: len(domains[i]))
            else:
                # Sin MRV, simplemente tomamos cualquiera (el orden del set).
                var = next(iter(unassigned))

            # La variable 'var' corresponde a la arista edges[var],
            # es decir, un par de islas (a,b).
            a, b = edges[var]

            # --------- EXPLORACIÓN DE VALORES ---------
            # Recorremos los valores posibles en su dominio.
            # sorted(..., reverse=True) hace que probemos primero 2, luego 1, luego 0.
            for val in sorted(domains[var], reverse=True):
                # Obtenemos cuántos puentes tiene actualmente esta arista en el Board.
                key = frozenset({a, b})
                info = board.bridges.get(key)
                k_current = info["k"] if info else 0

                # El solver trabaja "en modo creciente": sólo añadimos puentes,
                # nunca quitamos los que ya están en el Board.
                if val < k_current:
                    continue

                # delta = cuántos puentes nuevos vamos a intentar añadir para
                # alcanzar val desde k_current.
                delta = val - k_current

                # Intentamos aplicar esos puentes al Board.
                if delta > 0:
                    ok, _ = board.add_bridge(a, b, delta)
                    if not ok:
                        # Si no se puede añadir (por cruce, exceder número, etc.),
                        # esta asignación (var=val) es incompatible.
                        continue

                # En este punto, el Board refleja ya la decisión de que
                # la arista (a,b) tenga 'val' puentes (al menos temporalmente).

                # --------- PREPARAR ESTRUCTURAS PARA LA RAMA ---------
                # Clonamos dominios (copiando los sets).
                new_domains = {i: set(vs) for i, vs in domains.items()}
                # Clonamos el conjunto de variables no asignadas.
                new_unassigned = set(unassigned)

                # Fijamos el dominio de la variable actual a un único valor (val),
                # porque hemos decidido que en esta rama var == val.
                new_domains[var] = {val}
                new_unassigned.remove(var)

                # --------- FORWARD CHECKING / PROPAGACIÓN ---------
                if not propagate(new_domains, new_unassigned):
                    # Esta asignación lleva a un callejón sin salida.
                    # Deshacemos el cambio en el Board y probamos el siguiente valor.
                    if delta > 0:
                        board.remove_bridge(a, b, delta)
                    continue

                if verbose:
                    print(f"[BT] Arista {var} {a} - {b} = {val}")

                # --------- LLAMADA RECURSIVA ---------
                if backtrack(new_domains, new_unassigned):
                    # Si la recursión retorna True, significa que se encontró
                    # una solución completa en esta rama. Propagamos el True.
                    return True

                # --------- BACKTRACKING (DESHACER) ---------
                # Si la rama no llevó a una solución, deshacemos la modificación
                # en el Board antes de probar otro valor.
                if delta > 0:
                    board.remove_bridge(a, b, delta)

            # Si probamos todos los valores del dominio de la variable 'var'
            # y ninguno condujo a una solución, devolvemos False para indicar
            # que, con el estado actual de dominios, no hay solución posible.
            return False

        # Por último, llamamos a backtrack con las estructuras iniciales.
        return backtrack(domains, unassigned)
