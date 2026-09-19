"use client";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function QueuePage() {
  const [tickets, setTickets] = useState<any[]>([]);

  useEffect(() => {
    fetch(`${API_URL}/tickets?decision=escalate`)
      .then((r) => r.json())
      .then(setTickets)
      .catch(() => setTickets([]));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Escalation Queue</h1>
      {tickets.length === 0 ? (
        <p className="text-gray-500">No escalated tickets yet.</p>
      ) : (
        <table className="w-full text-sm bg-white border rounded">
          <thead>
            <tr className="border-b text-left">
              <th className="p-2">Intent</th>
              <th className="p-2">Category</th>
              <th className="p-2">Answer draft</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id} className="border-b">
                <td className="p-2">{t.intent}</td>
                <td className="p-2">{t.category}</td>
                <td className="p-2">{t.final_answer || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {/* TODO (Epic I2): sort/filter, and show the full reasoning trace per ticket */}
    </div>
  );
}
