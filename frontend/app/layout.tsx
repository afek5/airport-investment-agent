import type { Metadata, Viewport } from "next";
import { Instrument_Serif, JetBrains_Mono, Manrope } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { THEME_BOOT_SCRIPT } from "@/lib/theme-boot";
import "./globals.css";

const manrope = Manrope({ variable: "--font-manrope", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });
const serif = Instrument_Serif({ variable: "--font-instrument", subsets: ["latin"], weight: "400" });

export const metadata: Metadata = {
  title: "Airport Investment Intelligence",
  description: "Screen US airports for terminal investment with deterministic, sourced evidence.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0f0e0c" },
    { media: "(prefers-color-scheme: light)", color: "#f7f6f2" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`dark ${manrope.variable} ${mono.variable} ${serif.variable} h-full antialiased`}
      style={{ colorScheme: "dark" }}
    >
      <head>
        {/* Applies a saved light theme before first paint (dark is the default). */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="min-h-full">
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}
