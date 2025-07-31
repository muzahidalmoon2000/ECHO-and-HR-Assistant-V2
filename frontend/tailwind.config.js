export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
            boxShadow: {
        'custom-glow': '0 4px 20px rgba(0, 0, 0, 0.3)',
      },
    },
  },
plugins: [require('@tailwindcss/typography')],

}
