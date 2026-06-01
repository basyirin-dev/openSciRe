# SPDX-License-Identifier: Apache-2.0

"""Provenance DAG with cycle detection, topological sort, and Merkle root hashing."""

import hashlib
import json
from collections import deque
from datetime import datetime

from openscire.constants import ErrorCode
from openscire.exceptions import ProvenanceError
from openscire.models import ProvenanceEntry


class ProvenanceGraph:
    """In-memory DAG of provenance entries with cycle detection and traversal."""

    def __init__(self) -> None:
        self._nodes: dict[str, ProvenanceEntry] = {}
        self._parents: dict[str, list[str]] = {}
        self._children: dict[str, list[str]] = {}

    def add_entry(self, entry: ProvenanceEntry) -> None:
        """Add a provenance entry to the DAG after cycle and parent checks.

        Args:
            entry: The ProvenanceEntry to add.

        Raises:
            ProvenanceError: If a parent is missing or a cycle would be created.
        """
        action_id = entry.action_id
        if action_id in self._nodes:
            return

        for pid in entry.parent_ids:
            if pid not in self._nodes:
                msg = f"Parent entry {pid} not found in graph"
                raise ProvenanceError(
                    msg,
                    source="provenance.graph",
                    error_code=ErrorCode.PROV_CHAIN_BREAK,
                )

        self._nodes[action_id] = entry
        self._parents[action_id] = list(entry.parent_ids)

        if action_id not in self._children:
            self._children[action_id] = []
        for pid in entry.parent_ids:
            if pid not in self._children:
                self._children[pid] = []
            self._children[pid].append(action_id)

        if self._has_cycle():
            del self._nodes[action_id]
            del self._parents[action_id]
            self._children.pop(action_id, None)
            for pid in entry.parent_ids:
                if pid in self._children and action_id in self._children[pid]:
                    self._children[pid].remove(action_id)
            msg = "Adding this entry would create a cycle in the provenance DAG"
            raise ProvenanceError(
                msg,
                source="provenance.graph",
                error_code=ErrorCode.PROV_CHAIN_BREAK,
            )

    def get_entry(self, action_id: str) -> ProvenanceEntry | None:
        """Retrieve an entry by its action ID.

        Args:
            action_id: The action identifier.

        Returns:
            The ProvenanceEntry, or None if not found.
        """
        return self._nodes.get(action_id)

    def _has_cycle(self) -> bool:
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {nid: white for nid in self._nodes}

        def _dfs(nid: str) -> bool:
            color[nid] = gray
            for child in self._children.get(nid, []):
                if color.get(child, white) == gray:
                    return True
                if color.get(child, white) == white and _dfs(child):
                    return True
            color[nid] = black
            return False

        return any(color.get(nid, white) == white and _dfs(nid) for nid in self._nodes)

    def topological_sort(self) -> list[str]:
        """Return action IDs in topological order (Kahn's algorithm).

        Returns:
            List of action IDs ordered from earliest to latest.
        """
        in_degree: dict[str, int] = {}
        for nid in self._nodes:
            in_degree.setdefault(nid, 0)
            for child in self._children.get(nid, []):
                in_degree[child] = in_degree.get(child, 0) + 1

        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result: list[str] = []
        while queue:
            nid = queue.popleft()
            result.append(nid)
            for child in self._children.get(nid, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        return result

    def query(
        self,
        agent_id: str | None = None,
        action_type: str | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[ProvenanceEntry]:
        """Query entries by agent, action type, and/or time range.

        Args:
            agent_id: Filter by agent (optional).
            action_type: Filter by action type (optional).
            time_range: Inclusive (start, end) datetime range (optional).

        Returns:
            Sorted list of matching ProvenanceEntries.
        """
        results: list[ProvenanceEntry] = []
        for entry in self._nodes.values():
            if agent_id is not None and entry.agent_id != agent_id:
                continue
            if action_type is not None and entry.action_type != action_type:
                continue
            if time_range is not None:
                t = entry.timestamp
                if t < time_range[0] or t > time_range[1]:
                    continue
            results.append(entry)
        return sorted(results, key=lambda e: e.timestamp)

    def traverse(
        self,
        start_id: str,
        direction: str = "forward",
        max_depth: int = 100,
    ) -> list[ProvenanceEntry]:
        """BFS traversal from a starting node forward or backward.

        Args:
            start_id: Action ID to start from.
            direction: 'forward' (children) or 'backward' (parents).
            max_depth: Maximum traversal depth.

        Returns:
            List of entries reachable from start_id.
        """
        if start_id not in self._nodes:
            return []
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        result: list[ProvenanceEntry] = []
        while queue:
            nid, depth = queue.popleft()
            if nid in visited or depth > max_depth:
                continue
            visited.add(nid)
            result.append(self._nodes[nid])
            neighbors = (
                self._children.get(nid, [])
                if direction == "forward"
                else self._parents.get(nid, [])
            )
            for neighbor in neighbors:
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))
        return result

    def root_hash(self) -> str:
        """Compute a Merkle-style root hash over the entire DAG.

        Hashes each node with its children's hashes, producing a
        tamper-evident digest of the provenance state.

        Returns:
            Hex-encoded SHA-256 root hash.
        """
        order = self.topological_sort()
        if not order:
            return hashlib.sha256(b"empty").hexdigest()

        node_hashes: dict[str, str] = {}
        for nid in reversed(order):
            entry = self._nodes[nid]
            entry_data = entry.model_dump(mode="python", exclude={"cryptographic_signature"})
            child_hashes = sorted(
                node_hashes[c] for c in self._children.get(nid, []) if c in node_hashes
            )
            combined = (
                json.dumps(entry_data, sort_keys=True, default=str) + "|" + "|".join(child_hashes)
            )
            node_hashes[nid] = hashlib.sha256(combined.encode("utf-8")).hexdigest()

        roots = [nid for nid in order if nid not in self._parents or not self._parents[nid]]
        if roots:
            return hashlib.sha256(
                "".join(node_hashes[r] for r in roots).encode("utf-8")
            ).hexdigest()
        return node_hashes.get(order[-1], hashlib.sha256(b"empty").hexdigest())

    def __len__(self) -> int:
        return len(self._nodes)
