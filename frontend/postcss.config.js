/** Tailwind must run through PostCSS or no utility class (and no @apply) is ever generated. */
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
