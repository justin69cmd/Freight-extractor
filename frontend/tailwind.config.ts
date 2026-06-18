import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // confidence-band palette, reused across review + export views
        band: {
          high: "#16a34a",
          medium: "#d97706",
          low: "#dc2626",
        },
        brand: "#1f4e78",
      },
    },
  },
  plugins: [],
};
export default config;
