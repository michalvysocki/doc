// Sizes of the module map in pixels.
const MODULE_WIDTH = 200;
const MODULE_HEIGHT = 76;
const COLUMN_GAP = 24;
const LEVEL_GAP = 56;

function flatten(topics, rows = []) {
  for (const topic of topics) {
    rows.push(topic);
    flatten(topic.children, rows);
  }
  return rows;
}

export function isTopicCompleted(topic) {
  return topic.tasks_total > 0 && topic.tasks_solved === topic.tasks_total;
}

/**
 * Turns the course into a graph of its top-level modules. Topic links between
 * two modules become one edge with their count; an edge is "implied" when the
 * same order already follows from a path through other modules, so the overview
 * can hide it. Modules are placed in levels (one below the furthest module they
 * require), so every edge points down.
 */
export function moduleGraph(modules) {
  const moduleOf = {};
  const byId = {};
  for (const module of modules) {
    const topics = [module, ...flatten(module.children)];
    byId[module.id] = { ...module, topics };
    for (const topic of topics) moduleOf[topic.id] = module.id;
  }

  const pairs = new Map();
  for (const module of Object.values(byId)) {
    for (const topic of module.topics) {
      for (const requiredId of topic.requires) {
        const source = moduleOf[requiredId];
        if (!source || source === module.id) continue;
        const key = `${source}->${module.id}`;
        const pair = pairs.get(key) ?? {
          id: key,
          source,
          target: module.id,
          count: 0,
        };
        pair.count += 1;
        pairs.set(key, pair);
      }
    }
  }
  const edges = [...pairs.values()];

  const next = {};
  for (const { source, target } of edges) (next[source] ??= []).push(target);
  function reachesWithout(start, goal) {
    const stack = (next[start] ?? []).filter((id) => id !== goal);
    const seen = new Set();
    while (stack.length > 0) {
      const id = stack.pop();
      if (id === goal) return true;
      if (seen.has(id)) continue;
      seen.add(id);
      stack.push(...(next[id] ?? []));
    }
    return false;
  }
  for (const edge of edges) {
    edge.implied = reachesWithout(edge.source, edge.target);
  }

  // Links only point to earlier modules, so one pass in course order is enough.
  const levels = [];
  const levelOf = {};
  for (const module of modules) {
    const required = edges
      .filter((edge) => edge.target === module.id)
      .map((edge) => levelOf[edge.source] ?? 0);
    levelOf[module.id] = required.length > 0 ? Math.max(...required) + 1 : 0;
    (levels[levelOf[module.id]] ??= []).push(module);
  }

  const widest = Math.max(...levels.map((level) => level?.length ?? 0));
  const width = widest * MODULE_WIDTH + (widest - 1) * COLUMN_GAP;
  const nodes = [];
  levels.forEach((level, index) => {
    const rowWidth =
      level.length * MODULE_WIDTH + (level.length - 1) * COLUMN_GAP;
    level.forEach((module, column) => {
      const topics = byId[module.id].topics;
      nodes.push({
        id: module.id,
        type: "module",
        position: {
          x: (width - rowWidth) / 2 + column * (MODULE_WIDTH + COLUMN_GAP),
          y: index * (MODULE_HEIGHT + LEVEL_GAP),
        },
        width: MODULE_WIDTH,
        height: MODULE_HEIGHT,
        data: {
          title: module.title,
          total: topics.length,
          lessons: topics.filter((topic) => topic.has_explanation).length,
          completed: topics.filter(isTopicCompleted).length,
          reviewsDue: topics.reduce((sum, topic) => sum + topic.reviews_due, 0),
        },
      });
    });
  });
  return { nodes, edges, modules: byId, width };
}

/**
 * The topic with its direct prerequisites and the topics that require it, each
 * with the title of its module; null if the topic is not in the course.
 */
export function topicFocus(modules, topicId) {
  const all = modules.flatMap((module) =>
    [module, ...flatten(module.children)].map((topic) => ({
      ...topic,
      moduleTitle: module.title,
    })),
  );
  const byId = Object.fromEntries(all.map((topic) => [topic.id, topic]));
  const topic = byId[topicId];
  if (!topic) return null;
  return {
    topic,
    requires: topic.requires.filter((id) => id in byId).map((id) => byId[id]),
    requiredBy: all.filter((other) => other.requires.includes(topicId)),
  };
}
