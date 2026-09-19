import Link from "next/link";

export default function Home() {
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-4">Ticket Triage & Resolution Agent</h1>
      <p className="text-gray-600 mb-6">
        Starter frontend — see <Link href="/submit" className="underline">Submit Ticket</Link>,{" "}
        <Link href="/queue" className="underline">Escalation Queue</Link>, and{" "}
        <Link href="/dashboard" className="underline">Dashboard</Link>.
      </p>
    </div>
  );
}
