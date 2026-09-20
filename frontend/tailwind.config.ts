import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#12151A",
        surface: "#1B2027",
        "surface-raised": "#20262F",
        border: "#262B33",
        "text-primary": "#E7E9ED",
        "text-secondary": "#8890A0",
        resolve: "#4FB286",
        "resolve-dim": "#182E24",
        escalate: "#D9A15B",
        "escalate-dim": "#332616",
        denylist: "#C97267",
        "denylist-dim": "#311C1A",
      },
      fontFamily: {
        sans: ["var(--font-space-grotesk)", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["var(--font-plex-mono)", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      borderRadius: {
        DEFAULT: "4px",
      },
    },
  },
  plugins: [],
};
export default config;
