import { useMemo, useState } from "react";
import { Link } from "react-router";
import { ArrowRight, BookCheck, CircleCheck } from "lucide-react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Panel,
  Position,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { courseGraph } from "../utils/courseGraph";

// Same colours as --color-accent and --color-faint; SVG arrow markers need plain values.
const ACCENT = "#182f53";
const FAINT = "rgb(28 27 25 / 0.5)";

function Handles() {
  return (
    <>
      <Handle type="target" position={Position.Left} className="invisible" />
      <Handle type="source" position={Position.Right} className="invisible" />
    </>
  );
}

function TopicStatus({ data }) {
  return (
    <span className="ml-auto flex items-center gap-1 shrink-0">
      {data.reviewsDue > 0 && (
        <span className="rounded-full bg-accent/10 px-1.5 type-caption text-accent">
          {data.reviewsDue}
        </span>
      )}
      {data.hasExplanation && (
        <BookCheck
          size={12}
          className="text-accent"
          aria-label="Lesson ready"
        />
      )}
      {data.completed && (
        <CircleCheck
          size={12}
          className="text-good"
          aria-label="Topic completed"
        />
      )}
    </span>
  );
}

function ModuleNode({ data }) {
  return (
    <div
      className={`h-full rounded-md border bg-card px-3 pt-3 cursor-pointer ${
        data.selected ? "border-accent" : "border-line"
      } ${data.dimmed ? "opacity-40" : ""}`}
    >
      <Handles />
      <div className="flex items-center gap-2">
        <p className="type-label text-ink truncate min-w-0" title={data.title}>
          {data.title}
        </p>
        <TopicStatus data={data} />
      </div>
    </div>
  );
}

function TopicNode({ data }) {
  return (
    <div
      className={`h-full flex items-center gap-2 rounded-md border px-3 cursor-pointer hover:border-accent ${
        data.selected
          ? "border-accent bg-accent/5"
          : data.related
            ? "border-accent bg-paper"
            : "border-line bg-paper"
      } ${data.dimmed ? "opacity-40" : ""}`}
    >
      <Handles />
      <span
        className="type-caption text-ink truncate min-w-0"
        title={data.title}
      >
        {data.title}
      </span>
      <TopicStatus data={data} />
    </div>
  );
}

// Outside the component, so React Flow does not see new node types on every render.
const nodeTypes = { module: ModuleNode, topic: TopicNode };

function CourseMap({ course }) {
  const [selectedId, setSelectedId] = useState(null);
  const graph = useMemo(() => courseGraph(course.topics), [course.topics]);
  const selected = graph.topics[selectedId] ?? null;

  const { nodes, edges } = useMemo(() => {
    if (!selected) {
      return {
        nodes: graph.nodes,
        edges: graph.edges.map((edge) => ({
          ...edge,
          style: { stroke: FAINT, opacity: 0.3 },
          markerEnd: { type: MarkerType.ArrowClosed, color: FAINT },
        })),
      };
    }
    const own = graph.edges.filter(
      (edge) => edge.source === selected.id || edge.target === selected.id,
    );
    const related = new Set([
      selected.id,
      ...own.flatMap((edge) => [edge.source, edge.target]),
    ]);
    return {
      nodes: graph.nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          selected: node.id === selected.id,
          related: related.has(node.id),
          dimmed: !related.has(node.id),
        },
      })),
      edges: own.map((edge) => ({
        ...edge,
        zIndex: 1,
        style: { stroke: ACCENT, strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: ACCENT },
      })),
    };
  }, [graph, selected]);

  const requiresCount = edges.filter((e) => e.target === selectedId).length;
  const requiredByCount = edges.filter((e) => e.source === selectedId).length;

  return (
    <div className="h-[75vh] rounded-md border border-line bg-paper">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        onInit={async (flow) => {
          await flow.fitView({ nodes: graph.start, padding: 0.1 });
          const { x, zoom } = flow.getViewport();
          flow.setViewport({ x, y: 16, zoom });
        }}
        minZoom={0.2}
        onNodeClick={(_, node) =>
          setSelectedId((prev) => (prev === node.id ? null : node.id))
        }
        onPaneClick={() => setSelectedId(null)}
      >
        <Background />
        <Controls showInteractive={false} />
        {selected && (
          <Panel
            position="top-right"
            className="w-72 rounded-md border border-line bg-paper p-3 shadow-sm"
          >
            <p className="type-label text-ink">{selected.title}</p>
            <p className="type-caption text-muted mt-1 line-clamp-4">
              {selected.description}
            </p>
            <p className="type-caption text-faint mt-2">
              Requires {requiresCount} · required by {requiredByCount}
            </p>
            <Link
              to={`/courses/${course.id}/topics/${selected.id}`}
              className="inline-flex items-center gap-1 mt-2 type-body text-accent hover:underline"
            >
              {selected.has_explanation ? "Open lesson" : "Write lesson"}
              <ArrowRight size={14} />
            </Link>
          </Panel>
        )}
      </ReactFlow>
    </div>
  );
}

export default CourseMap;
