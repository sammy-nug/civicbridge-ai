/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#16211C",
        paper: "#F7F6F1",
        rule: "#D5D3C8",
        civic: { green: "#0B5D3B", greenDark: "#08472D", tint: "#E7F1EB" },
      },
      fontFamily: {
        // System fonts only, so no font download on slow or metered connections.
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Noto Sans", "sans-serif"],
        serif: ["Georgia", "Noto Serif", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
};
