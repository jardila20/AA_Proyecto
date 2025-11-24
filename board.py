from collections import deque

class Board:
    """
    Representa un tablero de Hashiwokakero con soporte para:
    - Carga de grilla (0-8)
    - Detección de islas y vecinos visibles (U,D,L,R)
    - Agregar/Quitar puentes (1 o 2) con validaciones:
        * Alineación H/V
        * Camino despejado (sin islas en medio)
        * No cruzar puentes ortogonales
        * Máximo 2 por par (no direccional)
        * No exceder el número de una isla
    - Render ASCII
    - Check de reglas y conectividad (un componente)
    Coordenadas internas: 0-based (r,c). Interfaz de consola usa 1-based.
    """
    H = "H"
    V = "V"

    def __init__(self, n_rows, n_cols, grid):
        self.n_rows = n_rows
        self.n_cols = n_cols
        self.grid = grid  # matriz de chars '0'..'8'
        # islas: lista de (r,c,valor)
        self.islands = [(r, c, int(self.grid[r][c]))
                        for r in range(n_rows)
                        for c in range(n_cols)
                        if self.grid[r][c].isdigit() and self.grid[r][c] != '0']
        # índice rápido para saber si una celda es isla
        self.is_island = {(r, c): val for (r, c, val) in self.islands}

        # bridges: dict clave frozenset({(r1,c1),(r2,c2)}) -> multiplicidad (0,1,2) y orientacion H/V
        self.bridges = {}  # key -> {"k": int, "dir": 'H'|'V'}

        # ocupación de “segmentos” entre celdas para detectar cruces
        # p.ej. para H usamos ("H", r, c) representando el segmento entre (r,c) y (r,c+1)
        # para V usamos ("V", r, c) representando el segmento entre (r,c) y (r+1,c)
        self.occupied_segments = set()

        # pre-cálculo de vecinos visibles
        self.visible_neighbors = {}  # (r,c) -> {"U": (r2,c2)|None, "D":..., "L":..., "R":...}
        self._precompute_visible_neighbors()

    # ----------- utilidades internas ------------
    def _precompute_visible_neighbors(self):
        for (r, c, _) in self.islands:
            vis = {"U": None, "D": None, "L": None, "R": None}
            # up
            rr = r - 1
            while rr >= 0:
                if (rr, c) in self.is_island:
                    vis["U"] = (rr, c)
                    break
                rr -= 1
            # down
            rr = r + 1
            while rr < self.n_rows:
                if (rr, c) in self.is_island:
                    vis["D"] = (rr, c)
                    break
                rr += 1
            # left
            cc = c - 1
            while cc >= 0:
                if (r, cc) in self.is_island:
                    vis["L"] = (r, cc)
                    break
                cc -= 1
            # right
            cc = c + 1
            while cc < self.n_cols:
                if (r, cc) in self.is_island:
                    vis["R"] = (r, cc)
                    break
                cc += 1
            self.visible_neighbors[(r, c)] = vis

    def _pair_key(self, a, b):
        return frozenset({a, b})

    def _orient(self, a, b):
        (r1, c1) = a
        (r2, c2) = b
        if r1 == r2:
            return self.H
        if c1 == c2:
            return self.V
        return None

    def _path_between(self, a, b):
        """Devuelve la lista de segmentos (orientados) entre a y b, excluyendo las celdas de islas.
           Para H: [("H", r, minc), ("H", r, minc+1), ..., ("H", r, maxc-1)]
           Para V: [("V", minr, c), ..., ("V", maxr-1, c)]
        """
        (r1, c1) = a
        (r2, c2) = b
        segs = []
        if r1 == r2:
            r = r1
            cstart = min(c1, c2)
            cend = max(c1, c2)
            for cc in range(cstart, cend):
                segs.append((self.H, r, cc))
        elif c1 == c2:
            c = c1
            rstart = min(r1, r2)
            rend = max(r1, r2)
            for rr in range(rstart, rend):
                segs.append((self.V, rr, c))
        return segs

    def degree(self, a):
        """Suma de puentes incidentes a la isla a=(r,c)."""
        total = 0
        for key, info in self.bridges.items():
            if info["k"] == 0:
                continue
            nodes = list(key)
            if a in nodes:
                total += info["k"]
        return total

    def pending(self, a):
        return self.is_island[a] - self.degree(a)

    # ----------- validaciones -----------
    def _visible_aligned(self, a, b):
        """Chequea que a y b sean vecinos visibles en línea recta sin islas en medio."""
        ori = self._orient(a, b)
        if not ori:
            return False
        # Debe ser exactamente el vecino más cercano en esa dirección
        vis = self.visible_neighbors[a]
        if ori == self.H:
            if b[1] > a[1]:
                return vis["R"] == b
            else:
                return vis["L"] == b
        else:  # V
            if b[0] > a[0]:
                return vis["D"] == b
            else:
                return vis["U"] == b

    def _crossing_if_add(self, a, b):
        """True si al agregar un puente (1 o 2) entre a y b se produce cruce con algún segmento ortogonal existente."""
        new_segs = self._path_between(a, b)
        for seg in new_segs:
            if seg in self.occupied_segments:
                typ, r, c = seg
                if typ == self.H:
                    if ("V", r, c) in self.occupied_segments:
                        return True
                else:
                    if ("H", r, c) in self.occupied_segments:
                        return True
        return False

    def can_add_bridge(self, a, b, k):
        """Valida si se pueden añadir k∈{1,2} puentes entre a y b."""
        if a not in self.is_island or b not in self.is_island:
            return (False, "Ambos extremos deben ser islas.")
        if k not in (1, 2):
            return (False, "k debe ser 1 o 2.")
        if not self._visible_aligned(a, b):
            return (False, "Islas no están alineadas como vecinas visibles.")
        key = self._pair_key(a, b)
        ori = self._orient(a, b)

        current = self.bridges.get(key, {"k": 0, "dir": ori})

        if current["k"] + k > 2:
            return (False, "Máximo 2 puentes entre las mismas islas.")

        # no cruzar
        if self._crossing_if_add(a, b):
            return (False, "El puente propuesto cruzaría otro puente.")

        # no exceder número de islas
        if self.degree(a) + k > self.is_island[a]:
            return (False, f"La isla {a} excedería su número.")
        if self.degree(b) + k > self.is_island[b]:
            return (False, f"La isla {b} excedería su número.")

        return (True, "OK")

    def add_bridge(self, a, b, k):
        ok, msg = self.can_add_bridge(a, b, k)
        if not ok:
            return (False, msg)
        key = self._pair_key(a, b)
        ori = self._orient(a, b)
        info = self.bridges.get(key, {"k": 0, "dir": ori})
        info["k"] += k
        info["dir"] = ori
        self.bridges[key] = info

        # ocupa segmentos
        segs = self._path_between(a, b)
        for s in segs:
            self.occupied_segments.add(s)
        return (True, "Puente agregado.")

    def can_remove_bridge(self, a, b, k):
        if a not in self.is_island or b not in self.is_island:
            return (False, "Ambos extremos deben ser islas.")
        if k not in (1, 2):
            return (False, "k debe ser 1 o 2.")
        key = self._pair_key(a, b)
        if key not in self.bridges or self.bridges[key]["k"] < k:
            return (False, "No hay tantos puentes para quitar.")
        return (True, "OK")

    def remove_bridge(self, a, b, k):
        ok, msg = self.can_remove_bridge(a, b, k)
        if not ok:
            return (False, msg)
        key = self._pair_key(a, b)
        self.bridges[key]["k"] -= k
        if self.bridges[key]["k"] == 0:
            # liberar segmentos del corredor
            segs = self._path_between(a, b)
            for s in segs:
                if s in self.occupied_segments:
                    self.occupied_segments.remove(s)
            del self.bridges[key]
        return (True, "Puente quitado.")

    # ----------- render ASCII -----------
    def render(self):
        """
        Construye un dibujo ASCII del tablero con las islas y los puentes actuales.
        Para más claridad se usa una grilla “doble”: 2*filas+1 por 2*cols+1.
        """
        h = 2 * self.n_rows + 1
        w = 2 * self.n_cols + 1
        canvas = [[" " for _ in range(w)] for _ in range(h)]

        # dibujar islas
        for (r, c, val) in self.islands:
            cr = 2 * r + 1
            cc = 2 * c + 1
            canvas[cr][cc] = str(val)

        # dibujar puentes
        for key, info in self.bridges.items():
            if info["k"] <= 0:
                continue
            a, b = list(key)
            (r1, c1) = a
            (r2, c2) = b
            if info["dir"] == self.H:
                r = 2 * r1 + 1
                cstart = min(c1, c2) * 2 + 2
                cend = max(c1, c2) * 2
                ch = "-" if info["k"] == 1 else "="
                for cc in range(cstart, cend, 2):
                    canvas[r][cc] = ch
            else:
                c = 2 * c1 + 1
                rstart = min(r1, r2) * 2 + 2
                rend = max(r1, r2) * 2
                ch = "|" if info["k"] == 1 else "║"
                for rr in range(rstart, rend, 2):
                    canvas[rr][c] = ch

        return "\n".join("".join(row) for row in canvas)

    # ----------- chequeos globales -----------
    def counts_ok(self):
        return all(self.degree((r, c)) == val for (r, c, val) in self.islands)

    def is_connected(self):
        """Con puentes actuales (multiplicidad > 0), ¿todas las islas quedan en un componente?"""
        if not self.islands:
            return True
        # grafo
        adj = { (r,c): set() for (r,c,_) in self.islands }
        for key, info in self.bridges.items():
            if info["k"] > 0:
                a, b = list(key)
                adj[a].add(b)
                adj[b].add(a)

        # BFS desde cualquiera
        start = (self.islands[0][0], self.islands[0][1])
        q = deque([start])
        seen = {start}
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        return len(seen) == len(self.islands)

    def full_check(self):
        """Valida reglas finales:
           - cada isla cumple su número
           - no hay cruces (se evita al agregar)
           - conectividad 1 componente
        """
        if not self.counts_ok():
            return (False, "Alguna isla no cumple su número.")
        if not self.is_connected():
            return (False, "El grafo no está conectado.")
        return (True, "OK")

    # ----------- validación de entrada -----------
    @staticmethod
    def parse_from_lines(lines):
        """lines: lista de líneas ya strip(). Valida formato y crea Board."""
        if not lines:
            raise ValueError("Archivo vacío.")
        if "," not in lines[0]:
            raise ValueError("Encabezado inválido. Use 'filas,columnas'.")
        try:
            n_rows, n_cols = map(int, lines[0].split(","))
        except Exception:
            raise ValueError("Encabezado inválido: no se pudo leer filas y columnas.")

        if len(lines[1:]) != n_rows:
            raise ValueError("Cantidad de filas no coincide con el encabezado.")

        grid = []
        for i, line in enumerate(lines[1:], start=1):
            if len(line) != n_cols:
                raise ValueError(f"Fila {i} no tiene {n_cols} columnas exactas.")
            row = []
            for ch in line:
                if ch < '0' or ch > '8':
                    raise ValueError(f"Caracter inválido '{ch}' en fila {i}. Debe ser 0..8.")
                row.append(ch)
            grid.append(row)
        return Board(n_rows, n_cols, grid)
