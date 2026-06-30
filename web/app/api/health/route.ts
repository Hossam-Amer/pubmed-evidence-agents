export const dynamic = "force-dynamic";

const API = process.env.PUBMED_EVIDENCE_AGENTS_API_URL ?? "http://localhost:8015";

export async function GET() {
  try {
    const r = await fetch(`${API}/health`, { cache: "no-store" });
    return Response.json(await r.json());
  } catch (e) {
    return Response.json(
      { status: "offline", error: String(e) },
      { status: 502 },
    );
  }
}
