import "./globals.css";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import Nav from "@/components/Nav";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata = {
  title: "Support Loop | Triage Ops Console",
  description: "AI ticket triage console: classification, knowledge retrieval, grounded drafting, and critic guardrails.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${plexMono.variable}`}>
      <body className="font-sans min-h-screen bg-base text-text-primary flex antialiased selection:bg-surface-raised">
        <Nav />
        <main className="flex-1 min-h-screen px-6 py-8 md:px-10 overflow-y-auto max-w-5xl">
          {children}
        </main>
      </body>
    </html>
  );
}
