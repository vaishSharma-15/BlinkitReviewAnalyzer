# Assets

`blinkit-logo.svg` — Blinkit app icon, from Wikimedia Commons
(https://commons.wikimedia.org/wiki/File:Blinkit-yellow-app-icon.svg),
uploaded by Hirebettu, licensed CC BY-SA 4.0.

"Blinkit" and its logo are trademarks of Blink Commerce Private Limited and are
used here only to identify the source of the reviews this tool analyses.

## blinkit-logo.png

The same mark rasterised to 256×256, used only as the browser tab icon.
`st.set_page_config(page_icon=…)` is handed straight to the browser as the favicon, and
browsers ignore an SVG there — pointed at the SVG, the tab showed Streamlit's own logo.
Regenerate from the SVG if the source ever changes.
