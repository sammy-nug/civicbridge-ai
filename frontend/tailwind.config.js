/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#102A43",
        civic: { blue: "#2563EB", green: "#16A34A", greenDark: "#166534", bg: "#F5F7FA" },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "Noto Sans", "sans-serif"],
      },
    },
  },
  plugins: [],
};
