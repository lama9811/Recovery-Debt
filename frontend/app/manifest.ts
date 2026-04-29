import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Recovery Debt",
    short_name: "Recovery Debt",
    description:
      "A bank statement for your body — recovery scores explained, simulated, and planned.",
    start_url: "/",
    display: "standalone",
    background_color: "#FAF7F2", // paper-100
    theme_color: "#1C2B22", // ink-800
    orientation: "portrait",
    categories: ["health", "fitness", "lifestyle"],
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
      {
        src: "/icon-mask.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable",
      },
      {
        src: "/favicon.ico",
        sizes: "any",
        type: "image/x-icon",
      },
    ],
  };
}
