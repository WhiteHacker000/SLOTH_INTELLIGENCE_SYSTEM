export class ApiError extends Error {}

interface ErrorBody {
  detail?: string | { msg: string }[];
}

function errorMessage(body: ErrorBody | null, status: number): string {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  // Validation errors arrive as a list; show the first in plain words.
  if (Array.isArray(detail) && detail.length > 0) {
    return detail[0].msg.replace(/^Value error, /, "");
  }
  return status >= 500 ? "The server had a problem. Try again." : "Request failed.";
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(data, response.status));
  return data as T;
}
