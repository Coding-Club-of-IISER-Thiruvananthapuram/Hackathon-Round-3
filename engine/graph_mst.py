"""
Graph and Minimum Spanning Tree (MST) Supply Network Engine.
Handles grid terrain step costs, Dijkstra shortest paths, Kruskal's MST,
supply line connectivity, and supply disruption/attrition.
"""
import heapq
from collections import deque
from typing import Dict, List, Tuple, Set, Any, Optional

GRID_WIDTH = 10
GRID_HEIGHT = 10

TERRAIN_COSTS = {
    "plain": 1.0,
    "forest": 2.0,
    "water": 3.0,
    "mountain": 999.0,  # Impassable
    "road": 0.5
}

def grid_distance(pos1: Tuple[int, int], pos2: Tuple[int, int], metric: str = "chebyshev") -> float:
    """Calculates distance on 2D grid. Chebyshev allows diagonal adjacency (standard 8-way)."""
    dx = abs(pos1[0] - pos2[0])
    dy = abs(pos1[1] - pos2[1])
    if metric == "chebyshev":
        return float(max(dx, dy))
    elif metric == "manhattan":
        return float(dx + dy)
    return float((dx ** 2 + dy ** 2) ** 0.5)

class DisjointSet:
    """Disjoint Set Union (DSU) for Kruskal's Minimum Spanning Tree."""
    def __init__(self, items):
        self.parent = {item: item for item in items}
        self.rank = {item: 0 for item in items}

    def find(self, item):
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, x, y) -> bool:
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x == root_y:
            return False
        if self.rank[root_x] < self.rank[root_y]:
            self.parent[root_x] = root_y
        elif self.rank[root_x] > self.rank[root_y]:
            self.parent[root_y] = root_x
        else:
            self.parent[root_y] = root_x
            self.rank[root_x] += 1
        return True


class GridGraph:
    def __init__(self, width: int = GRID_WIDTH, height: int = GRID_HEIGHT):
        self.width = width
        self.height = height
        self.terrain: Dict[Tuple[int, int], str] = {}
        self._initialize_default_map()

    def _initialize_default_map(self):
        """Creates a balanced, symmetrical 10x10 kingdom battlefield."""
        for x in range(self.width):
            for y in range(self.height):
                self.terrain[(x, y)] = "plain"

        # Mountain barriers / choke points
        mountains = [(3, 2), (3, 3), (6, 6), (6, 7), (4, 7), (5, 2)]
        for m in mountains:
            self.terrain[m] = "mountain"

        # Forest patches (give cover +2 def, cost 2 to traverse)
        forests = [
            (1, 4), (1, 5), (2, 5), (8, 4), (8, 5), (7, 4),
            (3, 8), (4, 8), (5, 1), (6, 1)
        ]
        for f in forests:
            self.terrain[f] = "forest"

        # River running across diagonally with 2 stone bridges
        rivers = [(4, 3), (4, 4), (5, 5), (5, 6)]
        for r in rivers:
            self.terrain[r] = "water"

    def get_step_cost(self, pos: Tuple[int, int], road_network: Optional[Set[Tuple[int, int]]] = None) -> float:
        """Returns the cost to enter a tile, reduced to 0.5 if an active road exists."""
        if road_network and pos in road_network:
            return TERRAIN_COSTS["road"]
        t = self.terrain.get(pos, "plain")
        return TERRAIN_COSTS.get(t, 1.0)

    def get_neighbors(
        self,
        pos: Tuple[int, int],
        impassable: Optional[Set[Tuple[int, int]]] = None
    ) -> List[Tuple[int, int]]:
        x, y = pos
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.terrain.get((nx, ny)) != "mountain":
                    if impassable is None or (nx, ny) not in impassable:
                        neighbors.append((nx, ny))
        return neighbors

    def find_shortest_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        road_network: Optional[Set[Tuple[int, int]]] = None,
        impassable: Optional[Set[Tuple[int, int]]] = None
    ) -> Tuple[float, List[Tuple[int, int]]]:
        """Dijkstra shortest path algorithm considering terrain and road network."""
        if start == goal:
            return 0.0, [start]

        queue = [(0.0, start, [start])]
        visited: Dict[Tuple[int, int], float] = {start: 0.0}

        while queue:
            cost, current, path = heapq.heappop(queue)

            if current == goal:
                return cost, path

            if cost > visited.get(current, float("inf")):
                continue

            for neighbor in self.get_neighbors(current, impassable=impassable):
                step_cost = self.get_step_cost(neighbor, road_network)
                if step_cost >= 999.0:
                    continue
                new_cost = cost + step_cost
                if new_cost < visited.get(neighbor, float("inf")):
                    visited[neighbor] = new_cost
                    heapq.heappush(queue, (new_cost, neighbor, path + [neighbor]))

        return float("inf"), []

    def compute_supply_mst(
        self,
        keep_pos: Tuple[int, int],
        captured_nodes: List[Tuple[int, int]]
    ) -> Dict[str, Any]:
        """
        Computes the Minimum Spanning Tree (MST) connecting the Kingdom Keep to all
        captured mines, outposts, and watchtowers with the minimum total step cost.
        Uses Kruskal's algorithm.
        """
        all_nodes = list(set([keep_pos] + captured_nodes))
        if len(all_nodes) <= 1:
            return {
                "nodes": all_nodes,
                "edges": [],
                "road_tiles": set([keep_pos]),
                "total_mst_cost": 0.0,
                "paths": {}
            }

        # Calculate all pairwise shortest paths
        pairwise_edges = []
        path_cache = {}

        for i in range(len(all_nodes)):
            for j in range(i + 1, len(all_nodes)):
                u, v = all_nodes[i], all_nodes[j]
                cost, path = self.find_shortest_path(u, v)
                if cost < float("inf"):
                    pairwise_edges.append((cost, u, v))
                    path_cache[(u, v)] = path
                    path_cache[(v, u)] = list(reversed(path))

        # Sort edges by weight for Kruskal's algorithm
        pairwise_edges.sort(key=lambda x: x[0])

        dsu = DisjointSet(all_nodes)
        mst_edges = []
        total_mst_cost = 0.0
        road_tiles: Set[Tuple[int, int]] = set()

        for cost, u, v in pairwise_edges:
            if dsu.union(u, v):
                mst_edges.append((u, v, cost))
                total_mst_cost += cost
                path = path_cache.get((u, v), [])
                for tile in path:
                    road_tiles.add(tile)

        return {
            "nodes": all_nodes,
            "edges": [{"from": list(u), "to": list(v), "cost": round(cost, 1)} for u, v, cost in mst_edges],
            "road_tiles": road_tiles,
            "total_mst_cost": round(total_mst_cost, 1),
            "paths": path_cache
        }

    def evaluate_supply_disruption(
        self,
        keep_pos: Tuple[int, int],
        captured_nodes: List[Tuple[int, int]],
        enemy_unit_positions: Set[Tuple[int, int]],
        mst_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Checks if enemy troops occupy any tile of the kingdom's MST road network.
        If an enemy cuts the supply line, severed nodes are flagged and lose income!
        """
        road_tiles: Set[Tuple[int, int]] = set(mst_info.get("road_tiles", []))
        disrupted_tiles = road_tiles.intersection(enemy_unit_positions)

        # Build an adjacency graph of connected road tiles excluding enemy occupied tiles
        passable_roads = road_tiles - disrupted_tiles
        passable_roads.add(keep_pos)

        # BFS from Keep using deque to find which nodes are still reachable
        reachable_nodes: Set[Tuple[int, int]] = set()
        queue = deque([keep_pos])
        visited_roads = set([keep_pos])

        while queue:
            curr = queue.popleft()
            if curr in captured_nodes or curr == keep_pos:
                reachable_nodes.add(curr)

            for neighbor in self.get_neighbors(curr):
                if neighbor in passable_roads and neighbor not in visited_roads:
                    visited_roads.add(neighbor)
                    queue.append(neighbor)

        severed_nodes = [node for node in captured_nodes if node not in reachable_nodes]

        return {
            "disrupted_tiles": [list(t) for t in disrupted_tiles],
            "severed_nodes": [list(n) for n in severed_nodes],
            "active_nodes": [list(n) for n in reachable_nodes],
            "is_line_cut": len(disrupted_tiles) > 0 or len(severed_nodes) > 0
        }
