from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from codecompass.storage.database import Database
from codecompass.storage.models import EntityRecord, FileRecord, RelationshipRecord
from codecompass.storage.repositories import EntityDAL, FileDAL, RelationshipDAL

IMPACT_RELATIONSHIPS = {"CALLS", "IMPORTS", "EXTENDS", "TESTS"}


class GraphImpactAnalyzer:
    """Computes downstream impact and risk ratings via reverse-dependency graph walks."""

    def __init__(
        self,
        files: list[FileRecord],
        entities: list[EntityRecord],
        relationships: list[RelationshipRecord],
    ) -> None:
        self.files = files
        self.entities = entities
        self.relationships = relationships

        # Indices
        self.entity_map = {e.id: e for e in entities}
        self.file_map = {f.id: f for f in files}
        self.reverse_adj: dict[str, list[RelationshipRecord]] = defaultdict(list)

        for rel in relationships:
            if rel.type in IMPACT_RELATIONSHIPS:
                # Reverse edge: if source CALLS target, changing target impacts source
                self.reverse_adj[rel.target_id].append(rel)

    @classmethod
    def from_database(cls, db: Database, repo_id: str) -> GraphImpactAnalyzer:
        file_dal = FileDAL(db)
        entity_dal = EntityDAL(db)
        rel_dal = RelationshipDAL(db)

        files = file_dal.get_files_for_repo(repo_id)
        entities = entity_dal.get_entities_for_repo(repo_id)
        relationships = rel_dal.get_relationships_for_repo(repo_id)

        return cls(files, entities, relationships)

    def _node_info(self, node_id: str, rel_type: str = "") -> dict[str, Any]:
        if node_id in self.entity_map:
            e = self.entity_map[node_id]
            f = self.file_map.get(e.file_id)
            return {
                "id": e.id,
                "name": e.name,
                "kind": e.kind,
                "file": f.path if f else "",
                "start_line": e.start_line,
                "end_line": e.end_line,
                "relation": rel_type,
            }
        elif node_id in self.file_map:
            f = self.file_map[node_id]
            return {
                "id": f.id,
                "name": f.path.split("/")[-1],
                "kind": "File",
                "file": f.path,
                "start_line": 1,
                "end_line": f.lines,
                "relation": rel_type,
            }
        return {"id": node_id, "name": node_id, "kind": "Unknown", "file": "", "relation": rel_type}

    def analyze_node(self, target_id: str, max_depth: int = 2) -> dict[str, Any]:
        """Runs a 2-hop reverse-dependency walk starting from target_id."""
        seen: set[str] = {target_id}
        queue: deque[tuple[str, int]] = deque([(target_id, 0)])
        affected_ids: set[str] = set()

        hop1_nodes: list[dict[str, Any]] = []
        hop2_nodes: list[dict[str, Any]] = []

        while queue:
            curr_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for rel in self.reverse_adj.get(curr_id, []):
                src = rel.source_id
                if src not in seen:
                    seen.add(src)
                    affected_ids.add(src)
                    info = self._node_info(src, rel.type)
                    if depth == 0:
                        hop1_nodes.append(info)
                    else:
                        hop2_nodes.append(info)
                    queue.append((src, depth + 1))

        # Categorize affected targets
        affected_files: set[str] = set()
        affected_apis: set[str] = set()
        affected_tests: set[str] = set()

        for aff_id in affected_ids:
            if aff_id in self.file_map:
                f = self.file_map[aff_id]
                affected_files.add(f.path)
                if f.is_test:
                    affected_tests.add(f.path)
            elif aff_id in self.entity_map:
                e = self.entity_map[aff_id]
                file_rec = self.file_map.get(e.file_id)
                if file_rec:
                    affected_files.add(file_rec.path)
                    if file_rec.is_test:
                        affected_tests.add(file_rec.path)
                if e.kind == "API":
                    affected_apis.add(e.name)

        # Risk scoring
        risk = "Low"
        if len(affected_files) >= 10 or len(affected_apis) >= 3:
            risk = "High"
        elif len(affected_files) >= 3 or len(affected_apis) >= 1:
            risk = "Medium"

        # Target label & metadata
        label = target_id
        target_kind = "File"
        target_file = ""
        line_range = None
        if target_id in self.entity_map:
            e = self.entity_map[target_id]
            label = e.name
            target_kind = e.kind
            f = self.file_map.get(e.file_id)
            target_file = f.path if f else ""
            line_range = [e.start_line, e.end_line]
        elif target_id in self.file_map:
            f = self.file_map[target_id]
            label = f.path
            target_file = f.path
            line_range = [1, f.lines]

        # Blast radius score calculation (0 - 100)
        blast_score = min(
            100,
            len(hop1_nodes) * 12 + len(hop2_nodes) * 6 + len(affected_apis) * 20 + len(affected_files) * 4,
        )

        recommendations: list[str] = []
        if risk == "High":
            recommendations.append(
                f"High blast radius: changing this entity cascades into {len(affected_files)} files and {len(affected_apis)} public API endpoints."
            )
        elif risk == "Medium":
            recommendations.append(f"Moderate impact: {len(affected_files)} downstream files rely on this component.")
        else:
            recommendations.append("Isolated component with minimal downstream blast radius.")

        if affected_tests:
            recommendations.append(f"Run tests in: {', '.join(sorted(affected_tests)[:3])}")
        else:
            recommendations.append("No automated test files detected directly covering this dependency path.")

        if affected_apis:
            recommendations.append(f"Verify public contracts for: {', '.join(sorted(affected_apis)[:3])}")

        return {
            "id": target_id,
            "label": label,
            "kind": target_kind,
            "type": target_kind,
            "file": target_file,
            "line_range": line_range,
            "affected_files": sorted(affected_files),
            "affected_apis": sorted(affected_apis),
            "affected_tests": sorted(affected_tests),
            "direct_dependents": hop1_nodes,
            "transitive_dependents": hop2_nodes,
            "blast_score": blast_score,
            "recommendations": recommendations,
            "risk": risk,
        }

    def build_impact_index(self) -> dict[str, dict[str, Any]]:
        """Builds an impact map for every File and Entity."""
        index: dict[str, dict[str, Any]] = {}
        for f in self.files:
            index[f.id] = self.analyze_node(f.id)
        for e in self.entities:
            index[e.id] = self.analyze_node(e.id)
        return index

