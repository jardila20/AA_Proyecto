#Versión documentada
from collections import deque

class Board:
    """
    Representa un tablero de Hashiwokakero con soporte para:
    - Carga de grilla (0-8)
    - Detección de islas y vecinos visibles (U,D,L,R)
    - Agregar/Quitar puentes (1 o 2) con validaciones:
        * Alineación horizontal o vertical
        * Camino despejado (sin islas en medio)
        * No cruzar puentes ortogonales
        * Máximo 2 puentes por par de islas (no direccional)
        * No exceder el número de una isla
    - Render ASCII del tablero (islas + puentes)
    - Chequeo de reglas finales y conectividad (un solo componente)

    NOTA:
    - Internamente las coordenadas se manejan en 0-based (r,c).
    - La interfaz por consola (main.py) trabaja en 1-based y convierte.
    """

    # Constantes para orientar los puentes
    H = "H"  # horizontal
    V = "V"  # vertical

    def __init__(self, n_rows, n_cols, grid):
        """
        n_rows: número de filas del tablero
        n_cols: número de columnas
        grid:   matriz (lista de listas) de caracteres '0'..'8'
        """
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.grid = grid  # matriz de chars '0'..'8'

        # Lista de islas:
        #   (r, c, valor)   donde valor es el número de la isla (1..8)
        self.islands = [
            (r, c, int(self.grid[r][c]))
            for r in range(n_rows)
            for c in range(n_cols)
            if self.grid[r][c].isdigit() and self.grid[r][c] != '0'
        ]

        # Diccionario rápido para saber si una celda es isla:
        #   (r,c) -> valor
        self.is_island = {
            (r, c): val
            for (r, c, val) in self.islands
        }

        # Diccionario de puentes:
        #   clave: frozenset({(r1,c1),(r2,c2)}) (par de islas, sin orden)
        #   valor: {"k": multiplicidad(0..2), "dir": 'H' o 'V'}
        #
        # Si k == 0, no se considera puente (se puede eliminar del dict).
        self.bridges = {}

        # Conjunto de "segmentos" ocupados entre celdas para detectar cruces.
        # Un segmento es una arista de la grilla entre dos celdas adyacentes:
        #   - horizontal: ("H", r, c) representa el segmento entre (r,c) y (r,c+1)
        #   - vertical:   ("V", r, c) representa el segmento entre (r,c) y (r+1,c)
        #
        # Guardamos TODOS los segmentos ocupados por puentes, sin distinguir
        # cuántos puentes pasan (k=1 o k=2) porque para cruces nos basta saber
        # que hay puente en ese "carril".
        self.occupied_segments = set()

        # Para cada isla, precomputamos qué otra isla ve en cada dirección:
        # visible_neighbors[(r,c)] = {"U": (r2,c2)|None, "D":..., "L":..., "R":...}
        # Esto evita tener que escanear filas/columnas todo el tiempo.
        self.visible_neighbors = {}
        self._precompute_visible_neighbors()

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _precompute_visible_neighbors(self):
        """
        Para cada isla, busca en las 4 direcciones (arriba, abajo, izquierda,
        derecha) la PRIMERA isla que aparezca, sin importar la distancia.
        Eso define los "vecinos visibles": los únicos con los que puede
        haber puentes directos.
        """
        for (r, c, _) in self.islands:
            vis = {"U": None, "D": None, "L": None, "R": None}

            # Buscar isla hacia arriba (fila decreciente)
            rr = r - 1
            while rr >= 0:
                if (rr, c) in self.is_island:
                    vis["U"] = (rr, c)
                    break
                rr -= 1

            # Buscar isla hacia abajo (fila creciente)
            rr = r + 1
            while rr < self.n_rows:
                if (rr, c) in self.is_island:
                    vis["D"] = (rr, c)
                    break
                rr += 1

            # Buscar isla hacia la izquierda (columna decreciente)
            cc = c - 1
            while cc >= 0:
                if (r, cc) in self.is_island:
                    vis["L"] = (r, cc)
                    break
                cc -= 1

            # Buscar isla hacia la derecha (columna creciente)
            cc = c + 1
            while cc < self.n_cols:
                if (r, cc) in self.is_island:
                    vis["R"] = (r, cc)
                    break
                cc += 1

            self.visible_neighbors[(r, c)] = vis

    def _pair_key(self, a, b):
        """Devuelve la clave de diccionario para el par de islas a,b (sin orden)."""
        return frozenset({a, b})

    def _orient(self, a, b):
        """
        Determina si el par de coordenadas a,b está alineado horizontal o vertical.
        Devuelve:
            'H' si están en la misma fila,
            'V' si están en la misma columna,
            None en caso contrario (no alineados).
        """
        (r1, c1) = a
        (r2, c2) = b
        if r1 == r2:
            return self.H
        if c1 == c2:
            return self.V
        return None

    def _path_between(self, a, b):
        """
        Devuelve la lista de segmentos (tipo, fila, col) que hay entre las celdas
        a y b, independientemente de cuántos puentes haya.
        NO incluye las celdas de las islas, solo los segmentos intermedios.

        Ejemplo:
          - Si a=(r,1) y b=(r,4) en la misma fila, se devuelven:
                ("H", r, 1), ("H", r, 2), ("H", r, 3)
            que representan los segmentos entre:
                (r,1)-(r,2), (r,2)-(r,3), (r,3)-(r,4)
        """
        (r1, c1) = a
        (r2, c2) = b
        segs = []
        if r1 == r2:
            # Camino horizontal
            r = r1
            cstart = min(c1, c2)
            cend = max(c1, c2)
            for cc in range(cstart, cend):
                segs.append((self.H, r, cc))
        elif c1 == c2:
            # Camino vertical
            c = c1
            rstart = min(r1, r2)
            rend = max(r1, r2)
            for rr in range(rstart, rend):
                segs.append((self.V, rr, c))
        return segs

    # ------------------------------------------------------------------
    # Grado / pendientes de una isla
    # ------------------------------------------------------------------
    def degree(self, a):
        """
        Devuelve la suma de puentes incidentes a la isla a=(r,c).
        Es decir, para todas las aristas que conectan a con otra isla,
        sumamos la multiplicidad k de cada una.
        """
        total = 0
        for key, info in self.bridges.items():
            if info["k"] == 0:
                continue
            nodes = list(key)
            if a in nodes:
                total += info["k"]
        return total

    def pending(self, a):
        """
        Devuelve cuántos puentes le faltan a la isla a=(r,c) para llegar a su número.
        """
        return self.is_island[a] - self.degree(a)

    # ------------------------------------------------------------------
    # Validaciones de visibilidad y cruces
    # ------------------------------------------------------------------
    def _visible_aligned(self, a, b):
        """
        Verifica que:
          - a y b están alineados horizontal o verticalmente.
          - b es exactamente el vecino visible más cercano de a
            en esa dirección (es decir, no hay otra isla en medio).

        Usamos la tabla precalculada de visible_neighbors.
        """
        ori = self._orient(a, b)
        if not ori:
            return False

        vis = self.visible_neighbors[a]
        if ori == self.H:
            if b[1] > a[1]:
                # b está a la derecha
                return vis["R"] == b
            else:
                # b está a la izquierda
                return vis["L"] == b
        else:
            if b[0] > a[0]:
                # b está abajo
                return vis["D"] == b
            else:
                # b está arriba
                return vis["U"] == b

    def _crossing_if_add(self, a, b):
        """
        Verifica si al agregar un puente entre a y b se produciría un cruce
        ortogonal con algún puente ya existente.

        Idea:
        - Obtenemos los segmentos del camino a-b (listado por _path_between).
        - Para cada segmento, miramos si ya está ocupado.
        - Si está ocupado con un segmento de la orientación ortogonal,
          entonces hay cruce.

        Ejemplo:
        - Queremos agregar un puente vertical (V) que pasa por (r,c).
        - Si en occupied_segments ya estaba ("H", r, c) significaría
          que hay un puente horizontal cruzando ahí -> cruce.
        """
        new_segs = self._path_between(a, b)

        for seg in new_segs:
            if seg in self.occupied_segments:
                typ, r, c = seg
                if typ == self.H:
                    # Ya hay un segmento horizontal; si además hay vertical,
                    # se cruzan en ese punto.
                    if ("V", r, c) in self.occupied_segments:
                        return True
                else:
                    # typ == self.V
                    if ("H", r, c) in self.occupied_segments:
                        return True
        return False

    # ------------------------------------------------------------------
    # Operaciones de agregar / quitar puentes
    # ------------------------------------------------------------------
    def can_add_bridge(self, a, b, k):
        """
        Verifica si se pueden añadir k (1 o 2) puentes entre las islas a y b,
        sin modificar realmente el tablero.
        Devuelve (ok:bool, mensaje:str).
        """
        if a not in self.is_island or b not in self.is_island:
            return (False, "Ambos extremos deben ser islas.")

        if k not in (1, 2):
            return (False, "k debe ser 1 o 2.")

        # Deben ser vecinos visibles directos en línea recta
        if not self._visible_aligned(a, b):
            return (False, "Islas no están alineadas como vecinas visibles.")

        key = self._pair_key(a, b)
        ori = self._orient(a, b)

        # Información actual de esa arista (si existe)
        current = self.bridges.get(key, {"k": 0, "dir": ori})

        # Máximo 2 puentes por par de islas
        if current["k"] + k > 2:
            return (False, "Máximo 2 puentes entre las mismas islas.")

        # No cruzar otros puentes
        if self._crossing_if_add(a, b):
            return (False, "El puente propuesto cruzaría otro puente.")

        # No exceder el número de las islas a y b
        if self.degree(a) + k > self.is_island[a]:
            return (False, f"La isla {a} excedería su número.")
        if self.degree(b) + k > self.is_island[b]:
            return (False, f"La isla {b} excedería su número.")

        return (True, "OK")

    def add_bridge(self, a, b, k):
        """
        Agrega k puentes entre a y b, si es válido.

        Devuelve (ok:bool, mensaje:str).
        Si ok=True, el estado interno (bridges + occupied_segments) se actualiza.
        """
        ok, msg = self.can_add_bridge(a, b, k)
        if not ok:
            return (False, msg)

        key = self._pair_key(a, b)
        ori = self._orient(a, b)
        info = self.bridges.get(key, {"k": 0, "dir": ori})
        info["k"] += k
        info["dir"] = ori
        self.bridges[key] = info

        # Marcamos como ocupados los segmentos del camino a-b.
        segs = self._path_between(a, b)
        for s in segs:
            self.occupied_segments.add(s)

        return (True, "Puente agregado.")

    def can_remove_bridge(self, a, b, k):
        """
        Verifica si es posible quitar k puentes entre a y b.
        No modifica realmente el tablero.
        """
        if a not in self.is_island or b not in self.is_island:
            return (False, "Ambos extremos deben ser islas.")
        if k not in (1, 2):
            return (False, "k debe ser 1 o 2.")

        key = self._pair_key(a, b)
        if key not in self.bridges or self.bridges[key]["k"] < k:
            return (False, "No hay tantos puentes para quitar.")
        return (True, "OK")

    def remove_bridge(self, a, b, k):
        """
        Quita k puentes entre a y b, si existe(n).
        Si la multiplicidad llega a 0, se libera el "corredor" de segmentos.
        """
        ok, msg = self.can_remove_bridge(a, b, k)
        if not ok:
            return (False, msg)

        key = self._pair_key(a, b)
        self.bridges[key]["k"] -= k

        # Si ya no quedan puentes, liberamos segmentos y removemos la entrada
        if self.bridges[key]["k"] == 0:
            segs = self._path_between(a, b)
            for s in segs:
                if s in self.occupied_segments:
                    self.occupied_segments.remove(s)
            del self.bridges[key]

        return (True, "Puente quitado.")

    # ------------------------------------------------------------------
    # Render ASCII del tablero
    # ------------------------------------------------------------------
    def render(self):
        """
        Construye un dibujo ASCII del tablero con las islas y los puentes actuales.

        Truco:
        ------
        Usamos una grilla "doble" de tamaño:
            alto = 2 * n_rows + 1
            ancho = 2 * n_cols + 1

        Donde:
            - Las celdas de islas van en las posiciones (2*r+1, 2*c+1).
            - Entre medio dejamos espacio para dibujar líneas y símbolos.

        Para puentes:
            - Horizontales:
                "-" si hay 1 puente
                "=" si hay 2 puentes
            - Verticales:
                "|" si hay 1 puente
                "║" si hay 2 puentes
        """
        h = 2 * self.n_rows + 1
        w = 2 * self.n_cols + 1

        # Inicializamos el "canvas" de caracteres vacíos
        canvas = [[" " for _ in range(w)] for _ in range(h)]

        # Dibujar islas (sus números) en posiciones impares (2*r+1,2*c+1)
        for (r, c, val) in self.islands:
            cr = 2 * r + 1
            cc = 2 * c + 1
            canvas[cr][cc] = str(val)

        # Dibujar puentes
        for key, info in self.bridges.items():
            if info["k"] <= 0:
                continue
            a, b = list(key)
            (r1, c1) = a
            (r2, c2) = b

            if info["dir"] == self.H:
                # Puente horizontal en la fila r1 (o r2, que es igual)
                r = 2 * r1 + 1
                # columnas de inicio y fin (en la grilla "doble")
                cstart = min(c1, c2) * 2 + 2
                cend = max(c1, c2) * 2
                ch = "-" if info["k"] == 1 else "="
                for cc in range(cstart, cend, 2):
                    canvas[r][cc] = ch
            else:
                # Puente vertical en la columna c1 (o c2)
                c = 2 * c1 + 1
                rstart = min(r1, r2) * 2 + 2
                rend = max(r1, r2) * 2
                ch = "|" if info["k"] == 1 else "║"
                for rr in range(rstart, rend, 2):
                    canvas[rr][c] = ch

        # Unimos filas en un solo string grande
        return "\n".join("".join(row) for row in canvas)

    # ------------------------------------------------------------------
    # Chequeos globales (usados por el solver y por CHECK)
    # ------------------------------------------------------------------
    def counts_ok(self):
        """
        Verifica que cada isla tenga exactamente tantos puentes incidentes
        como su número.
        """
        return all(
            self.degree((r, c)) == val
            for (r, c, val) in self.islands
        )

    def is_connected(self):
        """
        Verifica que el grafo de islas + puentes tenga un solo componente conexo.

        Implementación:
        - Construimos un grafo no dirigido: nodos = islas, aristas = pares con k>0.
        - Hacemos un BFS/DFS desde una isla cualquiera.
        - Comparamos cuántas islas visitamos vs total de islas.
        """
        if not self.islands:
            return True

        # Construimos lista de adyacencias
        adj = {(r, c): set() for (r, c, _) in self.islands}
        for key, info in self.bridges.items():
            if info["k"] > 0:
                a, b = list(key)
                adj[a].add(b)
                adj[b].add(a)

        # Tomamos cualquier isla como inicio
        start = (self.islands[0][0], self.islands[0][1])
        q = deque([start])
        seen = {start}

        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)

        # Si visitamos todas las islas, el grafo está conectado
        return len(seen) == len(self.islands)

    def full_check(self):
        """
        Valida las reglas finales del puzzle:

        1. Cada isla cumple su número (counts_ok).
        2. No hay cruces ni más de 2 puentes por par (eso se evitó al agregar).
        3. El grafo es un único componente conexo (is_connected).

        Devuelve (ok:bool, mensaje:str).
        """
        if not self.counts_ok():
            return (False, "Alguna isla no cumple su número.")
        if not self.is_connected():
            return (False, "El grafo no está conectado.")
        return (True, "OK")

    # ------------------------------------------------------------------
    # Validación de entrada y construcción del Board
    # ------------------------------------------------------------------
    @staticmethod
    def parse_from_lines(lines):
        """
        Construye un Board a partir de una lista de líneas de texto ya strip().

        Formato esperado:
            - Primera línea: "filas,columnas"
            - Luego 'filas' líneas con exactamente 'columnas' caracteres '0'..'8'.
        """
        if not lines:
            raise ValueError("Archivo vacío.")

        if "," not in lines[0]:
            raise ValueError("Encabezado inválido. Use 'filas,columnas'.")

        # Parsear números de filas y columnas
        try:
            n_rows, n_cols = map(int, lines[0].split(","))
        except Exception:
            raise ValueError("Encabezado inválido: no se pudo leer filas y columnas.")

        # Verificar cantidad de filas
        if len(lines[1:]) != n_rows:
            raise ValueError("Cantidad de filas no coincide con el encabezado.")

        grid = []
        # lines[1:] son las filas de la grilla
        for i, line in enumerate(lines[1:], start=1):
            if len(line) != n_cols:
                raise ValueError(f"Fila {i} no tiene {n_cols} columnas exactas.")
            row = []
            for ch in line:
                if ch < '0' or ch > '8':
                    raise ValueError(
                        f"Caracter inválido '{ch}' en fila {i}. Debe ser 0..8."
                    )
                row.append(ch)
            grid.append(row)

        # Crear el Board ya validado
        return Board(n_rows, n_cols, grid)
