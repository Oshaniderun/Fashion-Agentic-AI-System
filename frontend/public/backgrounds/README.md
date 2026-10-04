Drop your image here and set --app-bg-image in theme.css

Alternative (no code edit): set VITE_APP_BG_IMAGE=/backgrounds/your-image.jpg in frontend/.env
and restart the dev server — src/main.tsx applies it to the same variable at startup.

The photo is shown only in the main content area (right of the sidebar), under a soft
overlay defined by --app-bg-overlay so text stays readable.
