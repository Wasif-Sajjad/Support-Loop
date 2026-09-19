import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "Ticket Triage Agent",
  description: "AI-powered support ticket triage and resolution",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <nav className="border-b bg-white px-6 py-4 flex gap-6">
          <Link href="/submit" className="font-medium hover:underline">Submit Ticket</Link>
          <Link href="/queue" className="font-medium hover:underline">Escalation Queue</Link>
          <Link href="/dashboard" className="font-medium hover:underline">Dashboard</Link>
        </nav>
        <main className="p-6 max-w-4xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
