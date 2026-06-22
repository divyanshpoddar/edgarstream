import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0d1117",
        surface: "#161b22",
        "surface-2": "#1c2128",
        border: "#30363d",
        muted: "#8b949e",
        text: "#e6edf3",
        green: "#3fb950",
        blue: "#58a6ff",
        orange: "#ffa657",
        purple: "#bc8cff",
        red: "#f85149",
        yellow: "#d29922",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
