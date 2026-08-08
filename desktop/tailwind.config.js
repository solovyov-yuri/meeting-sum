/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Token values copied verbatim from docs/ui-reference/styles.css (:root).
        app: "#F6F7F8",
        panel: {
          DEFAULT: "#FFFFFF",
          soft: "#FBFCFD",
        },
        border: {
          DEFAULT: "#E3E6EA",
          strong: "#D3D8DF",
        },
        ink: {
          DEFAULT: "#171A1F",
          muted: "#6B7280",
          soft: "#8B95A1",
        },
        accent: {
          DEFAULT: "#2563EB",
          hover: "#1D4ED8",
          soft: "#EAF1FF",
        },
        ok: { DEFAULT: "#15803D", soft: "#EAF7EF", line: "#BBF7D0" },
        warn: { DEFAULT: "#B45309", soft: "#FFF7ED", line: "#FED7AA" },
        danger: { DEFAULT: "#B91C1C", soft: "#FEF2F2", line: "#FECACA" },
      },
      borderRadius: {
        // Small radii only (6-8px). Controls = 7px, cards = 8px.
        sm: "6px",
        DEFAULT: "7px",
        md: "7px",
        lg: "8px",
        card: "8px",
      },
      fontSize: {
        xs: ["11px", "16px"],
        sm: ["12px", "18px"],
        base: ["14px", "20px"],
        md: ["14px", "21px"],
        lg: ["16px", "24px"],
        xl: ["17px", "26px"],
      },
      boxShadow: {
        seg: "0 1px 2px rgba(23,26,31,0.08)",
        window: "0 20px 60px rgba(23,26,31,0.12)",
      },
    },
  },
  plugins: [],
};
