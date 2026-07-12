/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // AntD уже даёт reset; отключаем preflight, чтобы не конфликтовать со стилями AntD.
  corePlugins: { preflight: false },
  theme: { extend: {} },
  plugins: [],
};
