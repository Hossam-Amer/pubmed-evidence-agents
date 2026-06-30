import type { StreamItem } from "./types";

/**
 * Read an NDJSON stream (one JSON object per line) from a fetch Response,
 * invoking `onItem` for each parsed line. Tolerates partial chunks.
 */
export async function readNdjsonStream(
  res: Response,
  onItem: (item: StreamItem) => void,
): Promise<void> {
  if (!res.body) throw new Error("Response has no body to stream");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (!line) continue;
      try {
        onItem(JSON.parse(line) as StreamItem);
      } catch {
        /* ignore malformed line */
      }
    }
  }

  const tail = buffer.trim();
  if (tail) {
    try {
      onItem(JSON.parse(tail) as StreamItem);
    } catch {
      /* ignore */
    }
  }
}
