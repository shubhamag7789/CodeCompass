import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Search,
  Maximize2,
  FolderTree,
  ShieldAlert,
  FileCode,
  Sparkles,
  Send,
  Bot,
  User,
  X,
  ExternalLink,
  Loader2,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ChevronDown,
  Layers,
  ArrowRight,
  Focus,
} from 'lucide-react';
import { api } from '../../api/client';
import type { AnalysisData, GraphNode, GraphEdge, ChatMessage } from '../../types';

interface DependencyGraphProps {
  analysis: AnalysisData;
  onSelectImpactNode?: (nodeId: string) => void;
  onOpenFile?: (filePath: string) => void;
  activeRepoId?: string;
}

const TYPE_COLORS: Record<string, string> = {
  Repository: '#6366f1',
  Directory: '#94a3b8',
  File: '#0ea5e9',
  Class: '#a855f7',
  Function: '#10b981',
  Method: '#14b8a6',
  API: '#f59e0b',
  Endpoint: '#f59e0b',
  ExternalDependency: '#f43f5e',
};

export const DependencyGraph: React.FC<DependencyGraphProps> = ({
  analysis,
  onSelectImpactNode,
  onOpenFile,
  activeRepoId,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Search & Filter state
  const storageKey = `codecompass_graph_state_${activeRepoId || 'default'}`;

  const savedGraphState = useMemo(() => {
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw);
    } catch {}
    return null;
  }, [storageKey]);

  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchDropdownOpen, setIsSearchDropdownOpen] = useState(false);
  const [isExpandDropdownOpen, setIsExpandDropdownOpen] = useState(false);
  const [filterType, setFilterType] = useState<string>(() => {
    return savedGraphState?.filterType ?? 'all';
  });

  // Hierarchy & Graph Navigation state
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    if (savedGraphState?.expanded && Array.isArray(savedGraphState.expanded) && savedGraphState.expanded.length > 0) {
      return new Set(savedGraphState.expanded);
    }
    const rootId = 'repo:root';
    const hasRoot = (analysis.nodes || []).some((n) => n.id === rootId);
    return new Set(hasRoot ? [rootId] : analysis.nodes?.[0] ? [analysis.nodes[0].id] : []);
  });
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    return savedGraphState?.selectedId ?? null;
  });

  // Transform / Pan-Zoom state
  const [transform, setTransform] = useState<{ scale: number; panX: number; panY: number }>(() => {
    return (
      savedGraphState?.transform ?? {
        scale: 0.9,
        panX: 100,
        panY: 80,
      }
    );
  });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // Inline AI Assistant state
  const [isAiOpen, setIsAiOpen] = useState<boolean>(() => {
    return savedGraphState?.isAiOpen ?? true;
  });
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => {
    return savedGraphState?.chatMessages ?? [];
  });
  const [chatInput, setChatInput] = useState('');
  const [isAiLoading, setIsAiLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement | null>(null);

  // Persist graph state whenever it changes
  useEffect(() => {
    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify({
          expanded: Array.from(expanded),
          selectedId,
          filterType,
          transform,
          isAiOpen,
          chatMessages,
        })
      );
    } catch {}
  }, [storageKey, expanded, selectedId, filterType, transform, isAiOpen, chatMessages]);

  // Pre-index graph structures
  const graphIndex = useMemo(() => {
    const nodesById = new Map<string, GraphNode>();
    const childrenByParent = new Map<string, string[]>();
    const parentByChild = new Map<string, string>();
    const incomingRels = new Map<string, GraphEdge[]>();
    const outgoingRels = new Map<string, GraphEdge[]>();

    (analysis.nodes || []).forEach((n) => {
      nodesById.set(n.id, n);
    });

    (analysis.relationships || []).forEach((r) => {
      if (r.type === 'CONTAINS') {
        if (!childrenByParent.has(r.source)) childrenByParent.set(r.source, []);
        childrenByParent.get(r.source)!.push(r.target);
        parentByChild.set(r.target, r.source);
      } else {
        if (!outgoingRels.has(r.source)) outgoingRels.set(r.source, []);
        outgoingRels.get(r.source)!.push(r);

        if (!incomingRels.has(r.target)) incomingRels.set(r.target, []);
        incomingRels.get(r.target)!.push(r);
      }
    });

    return { nodesById, childrenByParent, parentByChild, incomingRels, outgoingRels };
  }, [analysis]);

  // Search Results
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    return (analysis.nodes || [])
      .filter((n) => {
        const matchLabel = (n.label || '').toLowerCase().includes(q);
        const matchPath = (n.path || '').toLowerCase().includes(q);
        const matchId = (n.id || '').toLowerCase().includes(q);
        return matchLabel || matchPath || matchId;
      })
      .slice(0, 10);
  }, [searchQuery, analysis.nodes]);

  // Compute visible nodes with anti-clutter spacing
  const visibleData = useMemo(() => {
    const visibleIdSet = new Set<string>();
    const rootId = 'repo:root';

    if (graphIndex.nodesById.has(rootId)) {
      visibleIdSet.add(rootId);
    } else if (analysis.nodes?.[0]) {
      visibleIdSet.add(analysis.nodes[0].id);
    }

    // Add immediate children of all expanded nodes
    expanded.forEach((parentId) => {
      const children = graphIndex.childrenByParent.get(parentId) || [];
      children.forEach((cid) => {
        if (graphIndex.nodesById.has(cid)) visibleIdSet.add(cid);
      });
    });

    // If a node is selected, include its immediate caller and callee connections
    if (selectedId && graphIndex.nodesById.has(selectedId)) {
      visibleIdSet.add(selectedId);
      const inc = (graphIndex.incomingRels.get(selectedId) || []).slice(0, 15);
      inc.forEach((r) => {
        if (graphIndex.nodesById.has(r.source)) visibleIdSet.add(r.source);
      });
      const out = (graphIndex.outgoingRels.get(selectedId) || []).slice(0, 15);
      out.forEach((r) => {
        if (graphIndex.nodesById.has(r.target)) visibleIdSet.add(r.target);
      });
    }

    // Filter by type if requested
    let visibleNodes = Array.from(visibleIdSet)
      .map((id) => graphIndex.nodesById.get(id)!)
      .filter(Boolean);

    if (filterType !== 'all') {
      const targetNorm = filterType.toLowerCase();
      visibleNodes = visibleNodes.filter((n) => {
        const t = (n.type || '').toLowerCase();
        return (
          t === 'repository' ||
          t === targetNorm ||
          expanded.has(n.id) ||
          n.id === selectedId
        );
      });
    }

    const finalSet = new Set(visibleNodes.map((n) => n.id));

    // Active visible edges
    const activeEdges: GraphEdge[] = [];
    (analysis.relationships || []).forEach((rel) => {
      if (!finalSet.has(rel.source) || !finalSet.has(rel.target)) return;

      if (rel.type === 'CONTAINS') {
        if (expanded.has(rel.source)) activeEdges.push(rel);
      } else {
        if (selectedId) {
          if (rel.target === selectedId || rel.source === selectedId) {
            activeEdges.push(rel);
          }
        } else {
          activeEdges.push(rel);
        }
      }
    });

    // Assign layout positions by column depth
    const depthMap = new Map<string, number>();
    depthMap.set(rootId, 0);

    const queue = [rootId];
    while (queue.length > 0) {
      const pid = queue.shift()!;
      const pDepth = depthMap.get(pid) || 0;
      const children = graphIndex.childrenByParent.get(pid) || [];
      children.forEach((cid) => {
        if (!depthMap.has(cid)) {
          depthMap.set(cid, pDepth + 1);
          queue.push(cid);
        }
      });
    }

    visibleNodes.forEach((node) => {
      if (!depthMap.has(node.id)) {
        const t = (node.type || '').toLowerCase();
        if (t === 'repository') depthMap.set(node.id, 0);
        else if (t === 'directory') depthMap.set(node.id, 1);
        else if (t === 'file') depthMap.set(node.id, 2);
        else if (t === 'class') depthMap.set(node.id, 3);
        else depthMap.set(node.id, 4);
      }
    });

    const columns = new Map<number, GraphNode[]>();
    visibleNodes.forEach((node) => {
      const col = depthMap.get(node.id) ?? 2;
      if (!columns.has(col)) columns.set(col, []);
      columns.get(col)!.push(node);
    });

    const sortedCols = Array.from(columns.keys()).sort((a, b) => a - b);
    const positions = new Map<string, { x: number; y: number; radius: number }>();

    const colSpacing = 300;
    const startX = 140;

    sortedCols.forEach((colKey, colIdx) => {
      const nodesInCol = columns.get(colKey)!;
      nodesInCol.sort((a, b) => (a.label || '').localeCompare(b.label || ''));

      // Adaptive vertical node spacing: scales comfortably when many nodes exist to avoid overlapping
      const nodeSpacing = nodesInCol.length > 20 ? 46 : nodesInCol.length > 10 ? 60 : 76;
      const colHeight = (nodesInCol.length - 1) * nodeSpacing;
      const startY = Math.max(80, (720 - colHeight) / 2);
      const x = startX + colIdx * colSpacing;

      nodesInCol.forEach((node, rowIdx) => {
        const y = startY + rowIdx * nodeSpacing;
        const norm = (node.type || '').toLowerCase();
        const radius =
          norm === 'repository' ? 18 : norm === 'directory' ? 14 : norm === 'file' ? 11 : 8;
        positions.set(node.id, { x, y, radius });
      });
    });

    return {
      nodes: visibleNodes,
      edges: activeEdges,
      positions,
    };
  }, [expanded, selectedId, filterType, graphIndex, analysis]);

  // Fit to Page / Center graph smoothly
  const handleFitView = useCallback(() => {
    if (visibleData.nodes.length === 0) return;
    let minX = Infinity,
      maxX = -Infinity,
      minY = Infinity,
      maxY = -Infinity;

    visibleData.positions.forEach((pos) => {
      minX = Math.min(minX, pos.x);
      maxX = Math.max(maxX, pos.x);
      minY = Math.min(minY, pos.y);
      maxY = Math.max(maxY, pos.y);
    });

    const canvas = canvasRef.current;
    if (!canvas) return;
    const w = canvas.clientWidth || 900;
    const h = canvas.clientHeight || 600;

    const graphW = maxX - minX + 280;
    const graphH = maxY - minY + 200;
    const scale = Math.min(1.2, Math.max(0.2, Math.min(w / graphW, h / graphH)));

    const panX = w / 2 - ((minX + maxX) / 2) * scale;
    const panY = h / 2 - ((minY + maxY) / 2) * scale;

    setTransform({ scale, panX, panY });
  }, [visibleData]);

  // Automatic trace / jump to target node
  const jumpToNode = useCallback(
    (nodeId: string) => {
      if (!graphIndex.nodesById.has(nodeId)) return;

      // Trace all ancestor parents up to root and expand all of them
      const newExpanded = new Set(expanded);
      let curr = nodeId;
      while (curr) {
        const parent = graphIndex.parentByChild.get(curr);
        if (parent) {
          newExpanded.add(parent);
          curr = parent;
        } else {
          break;
        }
      }

      setExpanded(newExpanded);
      setSelectedId(nodeId);
      setIsAiOpen(true);
      setIsSearchDropdownOpen(false);
      setSearchQuery('');

      const targetNode = graphIndex.nodesById.get(nodeId);
      if (targetNode) {
        setChatMessages([
          {
            id: `ctx-${Date.now()}`,
            role: 'assistant',
            content: `Tracing **${targetNode.label}** (${targetNode.type || 'Entity'}). ${
              targetNode.path ? `Located at \`${targetNode.path}\`.` : ''
            }\n\nAll parent modules expanded on the graph. Ask me anything about its architecture, callers, or contract!`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }

      // Smoothly center the canvas on the target node
      setTimeout(() => {
        const pos = visibleData.positions.get(nodeId);
        const canvas = canvasRef.current;
        if (pos && canvas) {
          const w = canvas.clientWidth || 900;
          const h = canvas.clientHeight || 600;
          const targetScale = Math.max(transform.scale, 0.9);
          setTransform({
            scale: targetScale,
            panX: w / 2 - pos.x * targetScale,
            panY: h / 2 - pos.y * targetScale,
          });
        }
      }, 50);
    },
    [expanded, graphIndex, visibleData.positions, transform.scale]
  );

  // Redraw Canvas
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;

    if (width === 0 || height === 0) return;

    if (canvas.width !== Math.floor(width * ratio) || canvas.height !== Math.floor(height * ratio)) {
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
    }

    ctx.save();
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);

    // Ambient dot grid
    ctx.save();
    ctx.fillStyle = 'rgba(148, 163, 184, 0.08)';
    const gridSize = 28 * transform.scale;
    const offX = ((transform.panX % gridSize) + gridSize) % gridSize;
    const offY = ((transform.panY % gridSize) + gridSize) % gridSize;
    for (let gx = offX; gx < width; gx += gridSize) {
      for (let gy = offY; gy < height; gy += gridSize) {
        ctx.beginPath();
        ctx.arc(gx, gy, 1, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();

    // Pan & Zoom
    ctx.translate(transform.panX, transform.panY);
    ctx.scale(transform.scale, transform.scale);

    const { edges, nodes, positions } = visibleData;
    const incomingSet = new Set(
      selectedId ? (graphIndex.incomingRels.get(selectedId) || []).map((r) => r.source) : []
    );
    const outgoingSet = new Set(
      selectedId ? (graphIndex.outgoingRels.get(selectedId) || []).map((r) => r.target) : []
    );

    // Draw Edges
    edges.forEach((edge) => {
      const a = positions.get(edge.source);
      const b = positions.get(edge.target);
      if (!a || !b) return;

      const isConnected = selectedId && (edge.source === selectedId || edge.target === selectedId);
      const isHierarchy = edge.type === 'CONTAINS';

      ctx.save();
      if (selectedId) {
        ctx.globalAlpha = isConnected ? 1.0 : 0.08;
      } else {
        ctx.globalAlpha = isHierarchy ? 0.35 : 0.6;
      }

      if (edge.target === selectedId) {
        // Incoming caller to selected (Emerald)
        ctx.strokeStyle = '#34d399';
        ctx.lineWidth = 2.4;
      } else if (edge.source === selectedId) {
        // Outgoing callee from selected (Cyan)
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.4;
      } else if (isHierarchy) {
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
        ctx.lineWidth = 1.4;
      } else {
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1.2;
      }

      // Bezier curve
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      const cpX = (a.x + b.x) / 2;
      ctx.bezierCurveTo(cpX, a.y, cpX, b.y, b.x, b.y);
      ctx.stroke();
      ctx.restore();
    });

    // Draw Nodes
    nodes.forEach((node) => {
      const pos = positions.get(node.id);
      if (!pos) return;

      const isSelected = selectedId === node.id;
      const isIncoming = incomingSet.has(node.id);
      const isOutgoing = outgoingSet.has(node.id);
      const isExpanded = expanded.has(node.id);
      const hasChildren = (graphIndex.childrenByParent.get(node.id) || []).length > 0;

      const normType = (node.type || '').toLowerCase();
      const baseColor =
        TYPE_COLORS[node.type] ||
        (normType === 'function'
          ? '#10b981'
          : normType === 'class'
          ? '#a855f7'
          : normType === 'api'
          ? '#f59e0b'
          : normType === 'directory'
          ? '#94a3b8'
          : '#0ea5e9');

      ctx.save();
      if (selectedId) {
        const isRelevant = isSelected || isIncoming || isOutgoing;
        ctx.globalAlpha = isRelevant ? 1.0 : 0.18;
      } else {
        ctx.globalAlpha = 1.0;
      }

      // Glow Ring
      if (isSelected) {
        ctx.shadowColor = '#38bdf8';
        ctx.shadowBlur = 18;
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, pos.radius + 5, 0, Math.PI * 2);
        ctx.stroke();
        ctx.shadowBlur = 0;
      } else if (isIncoming) {
        ctx.shadowColor = '#34d399';
        ctx.shadowBlur = 12;
        ctx.strokeStyle = '#34d399';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, pos.radius + 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.shadowBlur = 0;
      } else if (isOutgoing) {
        ctx.shadowColor = '#38bdf8';
        ctx.shadowBlur = 12;
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, pos.radius + 4, 0, Math.PI * 2);
        ctx.stroke();
        ctx.shadowBlur = 0;
      }

      // Core Circle
      ctx.fillStyle = baseColor;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, pos.radius, 0, Math.PI * 2);
      ctx.fill();

      // Inner white dot
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, Math.max(2.5, pos.radius * 0.35), 0, Math.PI * 2);
      ctx.fill();

      // Expandable [+] / [-] Badge
      if (hasChildren) {
        const badgeX = pos.x + pos.radius * 0.7;
        const badgeY = pos.y - pos.radius * 0.7;
        ctx.fillStyle = isExpanded ? '#f43f5e' : '#10b981';
        ctx.beginPath();
        ctx.arc(badgeX, badgeY, 6, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 9px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(isExpanded ? '-' : '+', badgeX, badgeY);
      }

      // Label Text
      ctx.fillStyle = isSelected ? '#ffffff' : '#e2e8f0';
      ctx.font = isSelected
        ? 'bold 12px "Plus Jakarta Sans", sans-serif'
        : '11px "Plus Jakarta Sans", sans-serif';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';

      const labelText = node.label || node.id;
      ctx.fillText(labelText, pos.x + pos.radius + 8, pos.y - 4);

      // Subtitle / Type Tag
      ctx.fillStyle = isSelected ? '#38bdf8' : '#64748b';
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.fillText((node.type || 'Entity').toUpperCase(), pos.x + pos.radius + 8, pos.y + 8);

      ctx.restore();
    });

    ctx.restore();
  }, [visibleData, transform, selectedId, expanded, graphIndex]);

  useEffect(() => {
    draw();
  }, [draw]);

  // Handle Canvas Resizing & Visibility transitions (e.g. tab switches)
  useEffect(() => {
    const handleResize = () => draw();
    window.addEventListener('resize', handleResize);

    let ro: ResizeObserver | null = null;
    if (containerRef.current && typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect.width > 0 && entry.contentRect.height > 0) {
            draw();
          }
        }
      });
      ro.observe(containerRef.current);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      if (ro) ro.disconnect();
    };
  }, [draw]);

  // Mouse Interactivity
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button !== 0) return;
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    setTransform((prev) => ({ ...prev, panX: prev.panX + dx, panY: prev.panY + dy }));
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    isDraggingRef.current = false;

    // Detect click
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const worldX = (mouseX - transform.panX) / transform.scale;
    const worldY = (mouseY - transform.panY) / transform.scale;

    let clickedNode: GraphNode | null = null;
    visibleData.positions.forEach((pos, id) => {
      const hitRadius = Math.max(16, pos.radius + 8);
      const dx = worldX - pos.x;
      const dy = worldY - pos.y;
      if (dx * dx + dy * dy <= hitRadius * hitRadius) {
        clickedNode = graphIndex.nodesById.get(id) || null;
      }
    });

    if (clickedNode) {
      handleNodeClick(clickedNode);
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    setTransform((prev) => {
      const nextScale = Math.min(2.5, Math.max(0.15, prev.scale * zoomFactor));
      return { ...prev, scale: nextScale };
    });
  };

  const handleNodeClick = (node: GraphNode) => {
    setSelectedId(node.id);
    setIsAiOpen(true);

    const hasChildren = (graphIndex.childrenByParent.get(node.id) || []).length > 0;
    if (hasChildren) {
      setExpanded((prev) => {
        const next = new Set(prev);
        if (next.has(node.id)) next.delete(node.id);
        else next.add(node.id);
        return next;
      });
    }

    setChatMessages([
      {
        id: `ctx-${Date.now()}`,
        role: 'assistant',
        content: `I'm analyzing **${node.label}** (${node.type || 'Entity'}). ${
          node.path ? `Located at \`${node.path}\`.` : ''
        }\n\nAsk me anything about its architecture, incoming callers, contract, or dependencies!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  // Progressive Uncluttered Expansion Options
  const handleExpandDirectoriesOnly = () => {
    // Expands all directories to reveal all files cleanly, without overwhelming with 230 function symbols
    const dirIds = new Set<string>();
    dirIds.add('repo:root');
    (analysis.nodes || []).forEach((n) => {
      const t = (n.type || '').toLowerCase();
      if (t === 'directory' || t === 'repository') {
        dirIds.add(n.id);
      }
    });
    setExpanded(dirIds);
    setTimeout(() => handleFitView(), 50);
  };

  const handleExpandAll = () => {
    const allParentIds = new Set<string>();
    graphIndex.childrenByParent.forEach((_, parentId) => {
      allParentIds.add(parentId);
    });
    setExpanded(allParentIds);
    setTimeout(() => handleFitView(), 50);
  };

  const handleCollapseAll = () => {
    const rootId = 'repo:root';
    setExpanded(new Set(graphIndex.nodesById.has(rootId) ? [rootId] : []));
    setSelectedId(null);
    setTimeout(() => handleFitView(), 50);
  };

  // Inline Node AI Copilot
  const handleSendNodeAiQuestion = async (customQuestion?: string) => {
    const q = customQuestion || chatInput.trim();
    if (!q || isAiLoading) return;

    if (!customQuestion) setChatInput('');

    const targetNode = selectedId ? graphIndex.nodesById.get(selectedId) : null;
    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      role: 'user',
      content: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setChatMessages((prev) => [...prev, userMsg]);
    setIsAiLoading(true);

    const contextualPrompt = targetNode
      ? `[Graph Context: Entity "${targetNode.label}" (${targetNode.type}) at ${targetNode.path || 'workspace'}]\nQuestion: ${q}`
      : q;

    try {
      const res = await api.sendChatMessage({
        question: contextualPrompt,
        repo_id: activeRepoId,
      });

      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: res.answer || 'No architectural details returned.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: res.sources,
      };

      setChatMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error reasoning about node: ${err.message || 'API error'}.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setChatMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsAiLoading(false);
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const selectedNode = selectedId ? graphIndex.nodesById.get(selectedId) : null;
  const selectedIncoming = selectedId ? graphIndex.incomingRels.get(selectedId) || [] : [];
  const selectedOutgoing = selectedId ? graphIndex.outgoingRels.get(selectedId) || [] : [];
  const selectedChildren = selectedId ? graphIndex.childrenByParent.get(selectedId) || [] : [];

  return (
    <div className="relative h-[calc(100vh-4rem)] w-full flex bg-[#0c101d] overflow-hidden select-none">
      {/* Main Canvas Area */}
      <div className="flex-1 flex flex-col h-full relative min-w-0">
        {/* Top Control Bar with Decluttered Controls */}
        <div className="h-14 px-4 border-b border-white/5 bg-[#0c101d]/95 backdrop-blur-md flex items-center justify-between gap-3 z-30 flex-shrink-0">
          <div className="flex items-center space-x-3 flex-shrink-0">
            {/* Automatic Trace Search Input */}
            <div className="relative w-64 sm:w-80 md:w-96 flex-shrink-0">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onFocus={() => setIsSearchDropdownOpen(true)}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setIsSearchDropdownOpen(true);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && searchResults.length > 0) {
                      jumpToNode(searchResults[0].id);
                    }
                  }}
                  placeholder="Search & automatically trace symbol..."
                  className="w-full bg-slate-900 border border-white/15 rounded-xl pl-9 pr-8 py-2 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50 shadow-inner"
                />
                {searchQuery && (
                  <button
                    onClick={() => {
                      setSearchQuery('');
                      setIsSearchDropdownOpen(false);
                    }}
                    className="absolute right-2.5 top-2.5 text-slate-400 hover:text-white"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Instant Search Autocomplete Dropdown */}
              {isSearchDropdownOpen && searchResults.length > 0 && (
                <div
                  onMouseDown={(e) => e.stopPropagation()}
                  className="absolute left-0 w-96 min-w-[340px] max-w-[90vw] top-12 rounded-2xl border border-cyan-500/40 bg-[#0e1629] shadow-2xl z-50 max-h-80 overflow-y-auto divide-y divide-white/5 backdrop-blur-2xl ring-1 ring-cyan-500/30 p-1.5 animate-in fade-in duration-150"
                >
                  <div className="px-3 py-1.5 text-[10px] font-mono text-cyan-400 uppercase tracking-wider font-bold">
                    Matching Entities ({searchResults.length})
                  </div>
                  {searchResults.map((m) => {
                    const normT = (m.type || '').toUpperCase();
                    let badgeBg = 'bg-slate-700/50 text-slate-300 border-slate-600';
                    if (normT === 'DIRECTORY') badgeBg = 'bg-slate-700/60 text-slate-300 border-slate-600';
                    else if (normT === 'FILE') badgeBg = 'bg-blue-500/20 text-blue-300 border-blue-500/30';
                    else if (normT === 'FUNCTION') badgeBg = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
                    else if (normT === 'API') badgeBg = 'bg-amber-500/20 text-amber-300 border-amber-500/30';
                    else if (normT === 'CLASS') badgeBg = 'bg-purple-500/20 text-purple-300 border-purple-500/30';

                    return (
                      <div
                        key={m.id}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          jumpToNode(m.id);
                        }}
                        className="p-3 hover:bg-cyan-500/15 cursor-pointer rounded-xl flex items-center justify-between transition-colors group gap-3"
                      >
                        <div className="truncate min-w-0 flex-1">
                          <div className="text-xs font-bold text-white group-hover:text-cyan-300 truncate font-mono">
                            {m.label}
                          </div>
                          {m.path && (
                            <div className="text-[10px] text-slate-400 group-hover:text-slate-300 truncate font-mono mt-0.5">
                              {m.path}
                              {m.line ? `:${m.line}` : ''}
                            </div>
                          )}
                        </div>
                        <span
                          className={`text-[9px] uppercase font-mono px-2 py-0.5 rounded-md border font-bold flex-shrink-0 whitespace-nowrap ${badgeBg}`}
                        >
                          {m.type}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Filter Type Selector */}
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-slate-900 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500/50"
            >
              <option value="all">All Types</option>
              <option value="Directory">Directories</option>
              <option value="File">Files</option>
              <option value="API">APIs</option>
              <option value="Function">Functions</option>
              <option value="Class">Classes</option>
            </select>
          </div>

          {/* Right Controls: Compact & Never Overlaps */}
          <div className="flex items-center space-x-2 flex-shrink-0">
            {/* Prominent Fit to Page Button */}
            <button
              onClick={handleFitView}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-300 font-bold text-xs transition-all active:scale-95 shadow-sm"
              title="Fit graph to page and center in view"
            >
              <Maximize2 className="w-3.5 h-3.5 text-cyan-400" />
              <span>Fit to Page</span>
            </button>

            {/* View / Expansion Dropdown Menu */}
            <div className="relative">
              <button
                onClick={() => setIsExpandDropdownOpen((prev) => !prev)}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-200 transition-all"
              >
                <span>Expand</span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {isExpandDropdownOpen && (
                <div
                  onMouseDown={(e) => e.stopPropagation()}
                  className="absolute right-0 top-10 w-44 rounded-xl border border-white/10 bg-[#0f172a] shadow-2xl z-50 p-1.5 space-y-1 animate-in fade-in duration-100 ring-1 ring-white/10"
                >
                  <button
                    onClick={() => {
                      handleExpandDirectoriesOnly();
                      setIsExpandDropdownOpen(false);
                    }}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium text-cyan-300 hover:bg-cyan-500/10 transition-all"
                  >
                    Expand Tree (Dirs)
                  </button>
                  <button
                    onClick={() => {
                      handleExpandAll();
                      setIsExpandDropdownOpen(false);
                    }}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-200 hover:bg-white/5 transition-all"
                  >
                    Expand All (Full)
                  </button>
                  <button
                    onClick={() => {
                      handleCollapseAll();
                      setIsExpandDropdownOpen(false);
                    }}
                    className="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:bg-white/5 transition-all"
                  >
                    Collapse Root
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Canvas Area */}
        <div
          ref={containerRef}
          onClick={() => {
            if (isSearchDropdownOpen) setIsSearchDropdownOpen(false);
            if (isExpandDropdownOpen) setIsExpandDropdownOpen(false);
          }}
          className="flex-1 w-full h-full relative overflow-hidden cursor-grab active:cursor-grabbing"
        >
          <canvas
            ref={canvasRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onWheel={handleWheel}
            className="w-full h-full block"
          />

          {/* Floating Zoom Controls Dock in Bottom-Right Corner */}
          <div className="absolute bottom-4 right-4 z-10 glass-panel p-1 rounded-xl border border-white/10 flex items-center space-x-1 shadow-2xl">
            <button
              onClick={() => setTransform((prev) => ({ ...prev, scale: Math.min(2.5, prev.scale * 1.15) }))}
              className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setTransform((prev) => ({ ...prev, scale: Math.max(0.15, prev.scale * 0.85) }))}
              className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleFitView}
              className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all"
              title="Fit to Page"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Canvas Floating Legend */}
          <div className="absolute bottom-4 left-4 glass-panel p-2.5 rounded-xl border border-white/10 flex items-center space-x-3 text-[10px] font-mono text-slate-400">
            <span className="flex items-center space-x-1">
              <span className="w-2.5 h-2.5 rounded-full bg-[#94a3b8]"></span>
              <span>Directory</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2.5 h-2.5 rounded-full bg-[#0ea5e9]"></span>
              <span>File</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]"></span>
              <span>Function</span>
            </span>
            <span className="flex items-center space-x-1">
              <span className="w-2.5 h-2.5 rounded-full bg-[#f59e0b]"></span>
              <span>API</span>
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400">Click node to expand/collapse</span>
          </div>
        </div>
      </div>

      {/* Right Drawer: INLINE Node Inspector & AI Assistant */}
      <div
        className={`w-96 flex-shrink-0 border-l border-white/5 bg-[#0c101d]/95 backdrop-blur-xl flex flex-col h-full transition-all duration-200 z-20 ${
          isAiOpen ? 'translate-x-0' : 'translate-x-full hidden'
        }`}
      >
        {selectedNode ? (
          <>
            {/* Header: Node Details */}
            <div className="p-4 border-b border-white/5 flex flex-col space-y-3 bg-[#111827]/40 flex-shrink-0">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                  {selectedNode.type || 'Entity'}
                </span>
                <span className="text-[10px] font-mono text-slate-400">
                  {selectedChildren.length > 0
                    ? `${selectedChildren.length} children`
                    : `${selectedIncoming.length} in / ${selectedOutgoing.length} out`}
                </span>
              </div>

              <div>
                <h3 className="text-base font-bold text-white font-mono truncate">
                  {selectedNode.label}
                </h3>
                {selectedNode.path && (
                  <div
                    onClick={() => onOpenFile && onOpenFile(selectedNode.path!)}
                    className="text-xs text-cyan-400/80 hover:text-cyan-300 font-mono truncate mt-0.5 cursor-pointer flex items-center space-x-1"
                    title="Open file in File Explorer"
                  >
                    <FileCode className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate">{selectedNode.path}</span>
                    {selectedNode.line && <span>:{selectedNode.line}</span>}
                    <ExternalLink className="w-3 h-3 flex-shrink-0 text-slate-500" />
                  </div>
                )}
              </div>

              {/* Quick Actions */}
              <div className="flex items-center space-x-2 pt-1">
                {selectedChildren.length > 0 && (
                  <button
                    onClick={() => {
                      setExpanded((prev) => {
                        const next = new Set(prev);
                        if (next.has(selectedNode.id)) next.delete(selectedNode.id);
                        else next.add(selectedNode.id);
                        return next;
                      });
                    }}
                    className="flex-1 py-1.5 px-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-slate-200 transition-all"
                  >
                    {expanded.has(selectedNode.id) ? 'Collapse Children' : 'Expand Children'}
                  </button>
                )}

                {onSelectImpactNode && (
                  <button
                    onClick={() => onSelectImpactNode(selectedNode.id)}
                    className="flex-1 py-1.5 px-2 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/30 text-xs font-semibold text-cyan-300 flex items-center justify-center space-x-1 transition-all"
                  >
                    <ShieldAlert className="w-3.5 h-3.5" />
                    <span>Blast Radius</span>
                  </button>
                )}
              </div>
            </div>

            {/* INLINE AI COPILOT SECTION FOR THIS NODE */}
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="p-3 border-b border-white/5 bg-slate-900/40 flex items-center justify-between flex-shrink-0">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-xs font-bold text-slate-200">
                    Ask AI About &ldquo;{selectedNode.label}&rdquo;
                  </span>
                </div>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  Gemini 3.5
                </span>
              </div>

              {/* Inline Messages List */}
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {chatMessages.map((msg) => {
                  const isUser = msg.role === 'user';
                  return (
                    <div
                      key={msg.id}
                      className={`flex items-start space-x-2 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
                    >
                      <div
                        className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 text-xs ${
                          isUser
                            ? 'bg-blue-600 text-white'
                            : 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                        }`}
                      >
                        {isUser ? <User className="w-3 h-3" /> : <Bot className="w-3 h-3" />}
                      </div>

                      <div
                        className={`max-w-[85%] rounded-xl p-3 text-xs leading-relaxed space-y-2 ${
                          isUser
                            ? 'bg-blue-600/90 text-white'
                            : 'glass-card border border-white/10 text-slate-200'
                        }`}
                      >
                        <div className="whitespace-pre-wrap font-sans text-xs">{msg.content}</div>

                        {/* Citations if any */}
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="pt-2 border-t border-white/10 flex flex-wrap gap-1">
                            {msg.citations.map((cite, i) => (
                              <button
                                key={i}
                                onClick={() => onOpenFile && onOpenFile(cite.file)}
                                className="text-[10px] font-mono text-cyan-300 bg-cyan-950/40 px-1.5 py-0.5 rounded border border-cyan-800/30 truncate max-w-[160px]"
                              >
                                {cite.file.split('/').pop()}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {isAiLoading && (
                  <div className="flex items-center space-x-2 text-xs text-slate-400 p-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-cyan-400" />
                    <span>Analyzing node in codebase context...</span>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Quick Prompt Chips */}
              <div className="p-2 border-t border-white/5 space-y-1.5 bg-slate-900/40 flex-shrink-0">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Quick Inquiries
                </div>
                <div className="flex flex-col space-y-1">
                  <button
                    onClick={() =>
                      handleSendNodeAiQuestion(
                        `What is the primary architectural responsibility of "${selectedNode.label}"?`
                      )
                    }
                    className="text-left text-[11px] text-cyan-300 hover:text-cyan-200 bg-white/5 hover:bg-white/10 p-1.5 rounded-lg border border-white/5 truncate transition-all"
                  >
                    • What is this node&apos;s responsibility?
                  </button>
                  <button
                    onClick={() =>
                      handleSendNodeAiQuestion(
                        `Who calls or depends on "${selectedNode.label}", and what breaks if modified?`
                      )
                    }
                    className="text-left text-[11px] text-cyan-300 hover:text-cyan-200 bg-white/5 hover:bg-white/10 p-1.5 rounded-lg border border-white/5 truncate transition-all"
                  >
                    • Who calls this &amp; what can break?
                  </button>
                  <button
                    onClick={() =>
                      handleSendNodeAiQuestion(
                        `Explain the implementation contract and data flow for "${selectedNode.label}".`
                      )
                    }
                    className="text-left text-[11px] text-cyan-300 hover:text-cyan-200 bg-white/5 hover:bg-white/10 p-1.5 rounded-lg border border-white/5 truncate transition-all"
                  >
                    • Explain contract and implementation details
                  </button>
                </div>

                {/* Inline Question Input Form */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendNodeAiQuestion();
                  }}
                  className="relative pt-1"
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask any question about this node..."
                    disabled={isAiLoading}
                    className="w-full bg-slate-950 border border-white/10 rounded-xl pl-3 pr-10 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
                  />
                  <button
                    type="submit"
                    disabled={isAiLoading || !chatInput.trim()}
                    className="absolute right-1.5 top-2.5 p-1 rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-40 text-slate-950 transition-all"
                  >
                    <Send className="w-3.5 h-3.5" />
                  </button>
                </form>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500 space-y-3">
            <FolderTree className="w-10 h-10 text-slate-600 stroke-[1.5]" />
            <div className="text-xs font-semibold text-slate-400">Select Any Node in the Graph</div>
            <p className="text-[11px] text-slate-500 leading-relaxed max-w-xs">
              Click on any directory, file, API, or function in the graph to inspect incoming/outgoing
              dependencies and chat with the AI Copilot directly right here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
