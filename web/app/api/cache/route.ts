export const dynamic = "force-dynamic";

const API = process.env.PUBMED_EVIDENCE_AGENTS_API_URL ?? "http://localhost:8015";

export async function DELETE() {
  try {
    const r = await fetch(`${API}/cache`, { method: "DELETE" });
    return Response.json(await r.json());
  } catch (e) {
    return Response.json(
      { status: "error", error: String(e) },
      { status: 502 },
    );
  }
}
