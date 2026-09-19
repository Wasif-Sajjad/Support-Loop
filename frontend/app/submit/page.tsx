"use client";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SubmitPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/tickets`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: text }),
      });
      setResult(await res.json());
    } catch (err) {
      setResult({ error: "Could not reach the backend. Is it running?" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Submit a Test Ticket</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <textarea
          className="border rounded p-3 h-32"
          placeholder="e.g. My kubernetes pod keeps crashlooping after the last deploy"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          type="submit"
          disabled={loading || !text}
          className="bg-black text-white rounded px-4 py-2 w-fit disabled:opacity-50"
        >
          {loading ? "Running pipeline..." : "Submit"}
        </button>
      </form>

      {result && (
        <pre className="mt-6 bg-white border rounded p-4 text-sm overflow-auto">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      {/* TODO (Epic I1): render the full agent-by-agent trace, not just the final JSON */}
    </div>
  );
}
