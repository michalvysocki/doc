import { useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { BookCheck, CircleCheck } from "lucide-react";
import {
  Background,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import TopicFocus from "./TopicFocus";
import TopicStatus from "./TopicStatus";
import { moduleGraph, topicFocus } from "../utils/moduleGraph";

// Same colours as --color-accent and --color-faint; SVG arrow markers need plain values.
const ACCENT = "#182f53";
const FAINT = "rgb(28 27 25 / 0.5)";

function ModuleNode({ data }) {
  return (
    <div
      className={`h-full rounded-md border bg-card px-3 py-2 cursor-pointer hover:border-accent ${
        data.selected
          ? "border-accent"
          : data.related
            ? "border-accent/50"
            : "border-line"
      } ${data.dimmed ? "opacity-40" : ""}`}
    >
      <Handle type="target" position={Position.Top} className="invisible" />
      <Handle type="source" position={Position.Bottom} className="invisible" />
      <p className="type-caption text-ink line-clamp-2" title={data.title}>
        {data.title}
      </p>
      <p className="flex items-center gap-2 mt-1 type-caption text-faint">
        {data.total} topics
        {data.lessons > 0 && (
          <span className="flex items-center gap-0.5 text-accent">
            <BookCheck size={12} aria-label="Lessons ready" />
            {data.lessons}
          </span>
        )}
        {data.completed > 0 && (
          <span className="flex items-center gap-0.5 text-good">
            <CircleCheck size={12} aria-label="Topics completed" />
            {data.completed}
          </span>
        )}
        {data.reviewsDue > 0 && (
          <span className="rounded-full bg-accent/10 px-1.5 text-accent">
            {data.reviewsDue}
          </span>
        )}
      </p>
    </div>
  );
}

// Outside the component, so React Flow does not see new node types on every render.
const nodeTypes = { module: ModuleNode };

function CourseMap({ course }) {
  const wrapper = useRef(null);
  const [selectedId, setSelectedId] = useState(null);
  const graph = useMemo(() => moduleGraph(course.topics), [course.topics]);
  const selected = graph.modules[selectedId] ?? null;

  const { nodes, edges } = useMemo(() => {
    if (!selected) {
      return {
        nodes: graph.nodes,
        edges: graph.edges
          .filter((edge) => !edge.implied)
          .map((edge) => ({
            ...edge,
            style: { stroke: FAINT },
            markerEnd: { type: MarkerType.ArrowClosed, color: FAINT },
          })),
      };
    }
    const own = graph.edges.filter(
      (edge) => edge.source === selected.id || edge.target === selected.id,
    );
    const related = new Set(own.flatMap((edge) => [edge.source, edge.target]));
    return {
      nodes: graph.nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          selected: node.id === selected.id,
          related: related.has(node.id),
          dimmed: node.id !== selected.id && !related.has(node.id),
        },
      })),
      edges: own.map((edge) => ({
        ...edge,
        label: String(edge.count),
        style: { stroke: ACCENT, strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: ACCENT },
      })),
    };
  }, [graph, selected]);

  const requires = edges.filter((edge) => edge.target === selectedId).length;
  const requiredBy = edges.filter((edge) => edge.source === selectedId).length;

  const [searchParams, setSearchParams] = useSearchParams();
  const focusedId = searchParams.get("topic");
  const focus = useMemo(
    () => (focusedId ? topicFocus(course.topics, focusedId) : null),
    [course.topics, focusedId],
  );
  const showTopic = (topicId) =>
    setSearchParams(
      topicId ? { view: "map", topic: topicId } : { view: "map" },
    );

  if (focus) {
    return (
      <TopicFocus
        courseId={course.id}
        focus={focus}
        onFocus={showTopic}
        onBack={() => showTopic(null)}
      />
    );
  }

  return (
    <>
      <div
        ref={wrapper}
        className="h-[65vh] rounded-md border border-line bg-paper"
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          minZoom={0.2}
          onInit={(flow) => {
            const width = wrapper.current.clientWidth;
            const zoom = Math.min(1, Math.max(0.5, (width - 32) / graph.width));
            flow.setViewport({
              x: (width - graph.width * zoom) / 2,
              y: 16,
              zoom,
            });
          }}
          onNodeClick={(_, node) =>
            setSelectedId((prev) => (prev === node.id ? null : node.id))
          }
          onPaneClick={() => setSelectedId(null)}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      {selected && (
        <section className="mt-3 rounded-md bg-card p-4">
          <h2 className="type-item text-ink">{selected.title}</h2>
          <p className="type-caption text-faint mt-1">
            Requires {requires} {requires === 1 ? "module" : "modules"} ·
            required by {requiredBy}
          </p>
          <ul className="mt-3 flex flex-col gap-1">
            {selected.topics.map((topic) => (
              <li key={topic.id}>
                <button
                  type="button"
                  onClick={() => showTopic(topic.id)}
                  className="w-full flex items-center gap-2 rounded-md bg-paper px-3 py-2 text-left hover:bg-line"
                >
                  <span className="type-body text-ink">{topic.title}</span>
                  <TopicStatus topic={topic} />
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

export default CourseMap;
