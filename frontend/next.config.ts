import type { NextConfig } from "next";

// Production: a static export served by FastAPI at "/" (SPEC §2).
// Development (`next dev`): proxy /api to the FastAPI dev server.
const isDev = process.env.NODE_ENV === "development";
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: isDev ? undefined : "export",
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  ...(isDev
    ? { async rewrites() { return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }]; } }
    : {}),
};

export default nextConfig;
