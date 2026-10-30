from datetime import date
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import uuid
import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB, Document as DocumentDB
from models.enums import DocumentStatus
from retrieval.models import SearchResult

logger = logging.getLogger(__name__)

# Pattern to extract entity codes (e.g. 'CORP-HR-01', 'SEC-POL-042', 'ISO-27001')
POLICY_CODE_PATTERN = re.compile(r"\b[A-Z]{2,6}(?:-[A-Z0-9]{2,6})+\b")


class KnowledgeGraphManager:
    """
    Constructs and manages in-memory NetworkX enterprise knowledge graphs.
    
    Node Types:
    - 'document': Document entities with status, version, effective date.
    - 'section': Hierarchical section breadcrumb nodes.
    - 'chunk': Text chunks with physical page and order indices.
    - 'entity': Domain policy codes and regulatory concepts.
    
    Edge Types:
    - 'has_section': Document -> Section
    - 'has_chunk': Section -> Chunk
    - 'next_chunk': Chunk[i] -> Chunk[i+1] (sequential cohesion)
    - 'supersedes': Document(v2) -> Document(v1)
    - 'mentions': Chunk -> Entity
    - 'references': Chunk -> Document (cross-document policy citation)
    
    Time Complexity:
    - O(V + E) where V is nodes (documents + chunks) and E is relational edges.
    """

    def __init__(self):
        # Maps organization_id -> nx.DiGraph
        self._org_graphs: Dict[uuid.UUID, nx.DiGraph] = {}

    def get_or_build_graph(
        self, session: Session, organization_id: uuid.UUID, force_rebuild: bool = False
    ) -> nx.DiGraph:
        """
        Retrieve or lazily construct the tenant knowledge graph.

        Args:
            session: SQLAlchemy session.
            organization_id: Organization tenant boundary.
            force_rebuild: If True, forces complete rebuild from database.

        Returns:
            NetworkX DiGraph for the organization.
        """
        if not force_rebuild and organization_id in self._org_graphs:
            return self._org_graphs[organization_id]

        g = nx.DiGraph()

        # 1. Fetch documents
        docs = session.scalars(
            select(DocumentDB).where(DocumentDB.organization_id == organization_id)
        ).all()
        doc_map: Dict[uuid.UUID, DocumentDB] = {}
        canonical_map: Dict[str, DocumentDB] = {}

        for doc in docs:
            doc_map[doc.id] = doc
            if doc.canonical_id:
                canonical_map[doc.canonical_id] = doc

            doc_node_id = f"doc:{doc.id}"
            g.add_node(
                doc_node_id,
                node_type="document",
                id=doc.id,
                name=doc.name,
                canonical_id=doc.canonical_id,
                version=doc.version,
                status=doc.status,
                effective_date=doc.effective_date,
            )

        # 2. Add supersedes lineage edges
        for doc in docs:
            if doc.supersedes_id and doc.supersedes_id in doc_map:
                g.add_edge(
                    f"doc:{doc.id}",
                    f"doc:{doc.supersedes_id}",
                    edge_type="supersedes",
                )

        # 3. Fetch chunks
        chunks = session.scalars(
            select(ChunkDB)
            .where(ChunkDB.organization_id == organization_id)
            .order_by(ChunkDB.document_id, ChunkDB.chunk_index)
        ).all()

        # Group chunks by document for sequential edge construction
        doc_chunks: Dict[uuid.UUID, List[ChunkDB]] = {}
        for c in chunks:
            doc_chunks.setdefault(c.document_id, []).append(c)

            chunk_node_id = f"chunk:{c.chunk_id}"
            g.add_node(
                chunk_node_id,
                node_type="chunk",
                id=c.chunk_id,
                document_id=c.document_id,
                document_name=c.document_name,
                canonical_id=doc_map.get(c.document_id, doc).canonical_id if c.document_id in doc_map else None,
                version=c.version,
                section_context=c.section_context,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                content=c.content,
                status=c.document_status,
            )

            # Section node
            if c.section_context:
                sec_node_id = f"sec:{c.document_id}:{c.section_context}"
                if not g.has_node(sec_node_id):
                    g.add_node(
                        sec_node_id,
                        node_type="section",
                        document_id=c.document_id,
                        title=c.section_context,
                    )
                    g.add_edge(f"doc:{c.document_id}", sec_node_id, edge_type="has_section")
                g.add_edge(sec_node_id, chunk_node_id, edge_type="has_chunk")
            else:
                g.add_edge(f"doc:{c.document_id}", chunk_node_id, edge_type="has_chunk")

            # Entity mention and cross-reference extraction
            policy_mentions = POLICY_CODE_PATTERN.findall(c.content)
            for code in set(policy_mentions):
                ent_node_id = f"entity:{code}"
                if not g.has_node(ent_node_id):
                    g.add_node(ent_node_id, node_type="entity", code=code)
                g.add_edge(chunk_node_id, ent_node_id, edge_type="mentions")

                # If entity code matches another canonical document, add cross-reference edge
                if code in canonical_map and canonical_map[code].id != c.document_id:
                    target_doc = canonical_map[code]
                    g.add_edge(
                        chunk_node_id,
                        f"doc:{target_doc.id}",
                        edge_type="references",
                    )

        # 4. Add sequential next_chunk edges
        for d_id, c_list in doc_chunks.items():
            for i in range(len(c_list) - 1):
                g.add_edge(
                    f"chunk:{c_list[i].chunk_id}",
                    f"chunk:{c_list[i + 1].chunk_id}",
                    edge_type="next_chunk",
                )
                # Bi-directional link for sequential context expansion
                g.add_edge(
                    f"chunk:{c_list[i + 1].chunk_id}",
                    f"chunk:{c_list[i].chunk_id}",
                    edge_type="prev_chunk",
                )

        self._org_graphs[organization_id] = g
        logger.info(
            "Constructed Knowledge Graph for org %s: %d nodes, %d edges",
            organization_id,
            g.number_of_nodes(),
            g.number_of_edges(),
        )
        return g


class GraphRAGRetriever:
    """
    Graph-Augmented Retrieval (GraphRAG) engine.
    
    Responsibilities:
    - Uses seed search results (from hybrid/reranker) as anchor nodes.
    - Expands graph neighborhoods to retrieve contextually linked information:
        * Sequential adjacent chunks (prev/next) to heal split boundaries.
        * Sibling chunks in the same section.
        * Cross-referenced policy documents.
    - Runs Personalized PageRank (PPR) rooted at seed nodes to compute structural relevance.
    - Strictly filters out nodes belonging to superseded documents.
    - Strictly maintains tenant isolation.
    """

    def __init__(self, kg_manager: Optional[KnowledgeGraphManager] = None):
        self.kg_manager = kg_manager or KnowledgeGraphManager()

    def expand_graph_context(
        self,
        session: Session,
        organization_id: uuid.UUID,
        seed_results: List[SearchResult],
        max_hop: int = 1,
        include_adjacent_chunks: bool = True,
        current_only: bool = True,
        top_k: int = 10,
    ) -> List[SearchResult]:
        """
        Expand seed chunks through graph traversal.

        Args:
            session: SQLAlchemy session.
            organization_id: Organization tenant UUID.
            seed_results: Anchor SearchResult items from hybrid/vector search.
            max_hop: Number of graph exploration hops.
            include_adjacent_chunks: Whether to automatically include immediately prior/next chunks.
            current_only: Whether to exclude nodes from superseded documents.
            top_k: Total maximum results to return.

        Returns:
            List of SearchResult items including seeds and graph-discovered related chunks.
        """
        if not seed_results:
            return []

        g = self.kg_manager.get_or_build_graph(session, organization_id)
        if g.number_of_nodes() == 0:
            return seed_results[:top_k]

        seed_chunk_ids: Set[uuid.UUID] = {r.chunk_id for r in seed_results}
        discovered_nodes: Dict[str, float] = {}

        # Initialize seed personalization vector for Personalized PageRank (PPR)
        personalization: Dict[str, float] = {}
        for r in seed_results:
            node_key = f"chunk:{r.chunk_id}"
            if g.has_node(node_key):
                personalization[node_key] = max(0.01, float(r.score))

        # Run Personalized PageRank rooted on seeds if seeds exist in graph
        if personalization:
            try:
                ppr_scores = nx.pagerank(g, alpha=0.85, personalization=personalization, max_iter=200, tol=1e-3)
            except Exception as e:
                logger.warning("Personalized PageRank computation fallback: %s", e)
                ppr_scores = {}
        else:
            ppr_scores = {}

        # Hop-based immediate neighborhood expansion
        for r in seed_results:
            node_key = f"chunk:{r.chunk_id}"
            if not g.has_node(node_key):
                continue

            # 1. Adjacent chunks (prev / next)
            if include_adjacent_chunks:
                for neighbor in g.successors(node_key):
                    edge_data = g.get_edge_data(node_key, neighbor)
                    if edge_data and edge_data.get("edge_type") in ("next_chunk", "prev_chunk"):
                        discovered_nodes[neighbor] = max(
                            discovered_nodes.get(neighbor, 0.0),
                            r.score * 0.9,
                        )

            # 2. General 1-hop traversal (cross references, entities)
            for neighbor in g.successors(node_key):
                edge_data = g.get_edge_data(node_key, neighbor)
                edge_type = edge_data.get("edge_type", "") if edge_data else ""
                if edge_type == "references":
                    # Target is a document node; find chunks of that document directly or via sections
                    for doc_neighbor in g.successors(neighbor):
                        n_type = g.nodes[doc_neighbor].get("node_type")
                        if n_type == "chunk":
                            discovered_nodes[doc_neighbor] = max(
                                discovered_nodes.get(doc_neighbor, 0.0),
                                r.score * 0.75,
                            )
                        elif n_type == "section":
                            for sec_child in g.successors(doc_neighbor):
                                if g.nodes[sec_child].get("node_type") == "chunk":
                                    discovered_nodes[sec_child] = max(
                                        discovered_nodes.get(sec_child, 0.0),
                                        r.score * 0.75,
                                    )
                elif edge_type == "mentions":
                    # Entity node; find other chunks mentioning this entity
                    for other_chunk in g.predecessors(neighbor):
                        if other_chunk != node_key and g.nodes[other_chunk].get("node_type") == "chunk":
                            discovered_nodes[other_chunk] = max(
                                discovered_nodes.get(other_chunk, 0.0),
                                r.score * 0.65,
                            )

        # Build merged results list
        combined_results: List[SearchResult] = list(seed_results)
        existing_cids = {r.chunk_id for r in combined_results}

        # Add discovered graph chunk nodes
        for node_id, graph_score in discovered_nodes.items():
            if not g.has_node(node_id):
                continue
            node_data = g.nodes[node_id]
            if node_data.get("node_type") != "chunk":
                continue

            chunk_id = node_data.get("id")
            if chunk_id in existing_cids:
                continue

            # Filter superseded documents if current_only is True
            if current_only and node_data.get("status") == DocumentStatus.SUPERSEDED:
                continue

            ppr_val = ppr_scores.get(node_id, 0.0)
            combined_score = 0.5 * graph_score + 0.5 * ppr_val

            sr = SearchResult(
                chunk_id=chunk_id,
                document_id=node_data.get("document_id"),
                document_name=node_data.get("document_name", ""),
                canonical_id=node_data.get("canonical_id"),
                version=node_data.get("version", ""),
                section_context=node_data.get("section_context", ""),
                page_number=node_data.get("page_number", 1),
                content=node_data.get("content", ""),
                score=combined_score,
                rank=len(combined_results) + 1,
                source_method="graph",
                metadata={"graph_score": graph_score, "ppr_score": ppr_val},
            )
            combined_results.append(sr)
            existing_cids.add(chunk_id)

        # Sort combined results descending by score
        combined_results.sort(key=lambda x: x.score, reverse=True)

        # Update ranks
        final_list = []
        for rank, res in enumerate(combined_results[:top_k], start=1):
            res.rank = rank
            final_list.append(res)

        return final_list
