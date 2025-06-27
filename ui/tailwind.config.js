/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        magenta: "#E20074",        // T-Mobile brand color
        "magenta-dark": "#B0005A", // darker shade for hover / gradient
      },
    },
  },
  plugins: [],
}

