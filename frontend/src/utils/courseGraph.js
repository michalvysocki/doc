// Sizes of the course map in pixels.
const TOPIC_WIDTH = 240;
const TOPIC_HEIGHT = 40;
const GAP = 8;
const INDENT = 16;
const HEADER = 48;
const PADDING = 12;
const MODULE_GAP = 48;
const COLUMNS = 4;
const MODULE_WIDTH = TOPIC_WIDTH + 2 * PADDING;

function flatten(topics, depth = 0, rows = []) {
  for (const topic of topics) {
    rows.push({ topic, depth });
    flatten(topic.children, depth + 1, rows);
  }
  return rows;
}

function nodeData(topic) {
  return {
    title: topic.title,
    hasExplanation: topic.has_explanation,
    completed:
      topic.tasks_total > 0 && topic.tasks_solved === topic.tasks_total,
    reviewsDue: topic.reviews_due,
  };
}

/**
 * Lays the course out as a grid of modules (top-level topics) in course order,
 * each with its topics stacked inside it; deeper topics are indented.
 * Parents come before their children, as React Flow needs. Edges go from a
 * prerequisite to the topic that requires it.
 */
export function courseGraph(topics) {
  const modules = topics.map((module) => {
    const rows = flatten(module.children);
    return {
      module,
      rows,
      height: HEADER + rows.length * (TOPIC_HEIGHT + GAP) + PADDING,
    };
  });

  const rowTops = [0];
  for (let start = 0; start < modules.length; start += COLUMNS) {
    const tallest = Math.max(
      ...modules.slice(start, start + COLUMNS).map(({ height }) => height),
    );
    rowTops.push(rowTops.at(-1) + tallest + MODULE_GAP);
  }

  const byId = {};
  const nodes = [];
  modules.forEach(({ module, rows, height }, index) => {
    byId[module.id] = module;
    nodes.push({
      id: module.id,
      type: "module",
      position: {
        x: (index % COLUMNS) * (MODULE_WIDTH + MODULE_GAP),
        y: rowTops[Math.floor(index / COLUMNS)],
      },
      width: MODULE_WIDTH,
      height,
      data: nodeData(module),
    });
    rows.forEach(({ topic, depth }, row) => {
      byId[topic.id] = topic;
      nodes.push({
        id: topic.id,
        type: "topic",
        parentId: module.id,
        position: {
          x: PADDING + depth * INDENT,
          y: HEADER + row * (TOPIC_HEIGHT + GAP),
        },
        width: TOPIC_WIDTH - depth * INDENT,
        height: TOPIC_HEIGHT,
        data: nodeData(topic),
      });
    });
  });

  const edges = [];
  for (const topic of Object.values(byId)) {
    for (const requiredId of topic.requires) {
      if (requiredId in byId) {
        edges.push({
          id: `${requiredId}->${topic.id}`,
          source: requiredId,
          target: topic.id,
        });
      }
    }
  }
  const start = modules
    .slice(0, COLUMNS)
    .map(({ module }) => ({ id: module.id }));
  return { nodes, edges, topics: byId, start };
}
