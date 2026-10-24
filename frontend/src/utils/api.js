export const API_URL = "http://localhost:8000";

export function fileContentUrl(fileUuid) {
  return `${API_URL}/files/${fileUuid}/content`;
}

async function responseError(response) {
  const errorData = await response.json().catch(() => ({}));
  return new Error(
    typeof errorData.detail === "string"
      ? errorData.detail
      : `Request failed: ${response.status}`,
  );
}

export async function fetchJson(path, options) {
  const response = await fetch(`${API_URL}${path}`, options);

  if (!response.ok) throw await responseError(response);

  if (response.status === 204) return null;

  return response.json();
}

// Reads a response streamed as JSON lines (NDJSON) and calls onEvent for every line.
export async function streamJson(path, options, onEvent) {
  const response = await fetch(`${API_URL}${path}`, options);

  if (!response.ok) throw await responseError(response);

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    // The last piece may be a line that has not fully arrived yet.
    buffer = lines.pop();
    for (const line of lines) {
      if (line.trim()) onEvent(JSON.parse(line));
    }
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer));
}
