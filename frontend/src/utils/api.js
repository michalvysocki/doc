export const API_URL = "http://localhost:8000";

export function fileContentUrl(fileUuid) {
  return `${API_URL}/files/${fileUuid}/content`;
}

export async function fetchJson(path, options) {
  const response = await fetch(`${API_URL}${path}`, options);

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      typeof errorData.detail === "string"
        ? errorData.detail
        : `Request failed: ${response.status}`,
    );
  }

  if (response.status === 204) return null;

  return response.json();
}
