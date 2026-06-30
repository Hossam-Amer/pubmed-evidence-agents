import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API = process.env.PUBMED_EVIDENCE_AGENTS_API_URL ?? "http://localhost:8015";

/**
 * Proxy the browser's multipart form to the FastAPI `/query/stream` endpoint and
 * pipe its NDJSON response straight back, unbuffered. Same-origin from the
 * browser's perspective → no CORS, backend URL stays server-side.
 */
export async function POST(req: NextRequest) {
  const form = await req.formData();

  let upstream: Response;
  try {
    upstream = await fetch(`${API}/query/stream`, {
      method: "POST",
      body: form,
    });
  } catch (e) {
    const line =
      JSON.stringify({
        type: "error",
        data: { message: `Cannot reach pubmed-evidence-agents backend at ${API}: ${String(e)}` },
      }) + "\n";
    return new Response(line, {
      status: 200,
      headers: { "Content-Type": "application/x-ndjson" },
    });
  }

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "");
    const line =
      JSON.stringify({
        type: "error",
        data: { message: `Backend ${upstream.status}: ${text.slice(0, 300)}` },
      }) + "\n";
    return new Response(line, {
      status: 200,
      headers: { "Content-Type": "application/x-ndjson" },
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "application/x-ndjson",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}
