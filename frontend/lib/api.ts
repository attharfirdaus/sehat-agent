import type { ChatEvent } from "@/lib/types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  init?: { method?: string; body?: unknown },
): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: init?.method ?? "GET",
    headers:
      init?.body === undefined
        ? undefined
        : { "content-type": "application/json" },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (!res.ok) {
    const detail = await res.json().then(
      (j) => j.detail,
      () => res.statusText,
    );
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

/** Request yang dijawab SSE (/api/chat, /api/chat/resume, /api/checkin, /api/chat/stream). */
export async function streamChat(
  path: string,
  body: unknown,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  // body undefined = GET (sambung ulang ke giliran yang masih berjalan).
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers:
      body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(res.status, res.statusText);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      const data: string[] = [];
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      }
      if (data.length)
        onEvent({ event, data: JSON.parse(data.join("\n")) } as ChatEvent);
    }
  }
}
