import type { Metadata } from "next";
import { Instrument_Serif, JetBrains_Mono, Manrope } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

const manrope = Manrope({ variable: "--font-manrope", subsets: ["latin"] });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"] });
const serif = Instrument_Serif({ variable: "--font-instrument", subsets: ["latin"], weight: "400" });

export const metadata: Metadata = {
  title: "Airport Investment Intelligence",
  description: "Screen US airports for terminal investment with deterministic, sourced evidence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${manrope.variable} ${mono.variable} ${serif.variable} h-full antialiased`}>
      <body className="min-h-full">
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}
