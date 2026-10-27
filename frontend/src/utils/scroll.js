export function scrollToTask(taskId) {
  document
    .getElementById(`task-${taskId}`)
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}
