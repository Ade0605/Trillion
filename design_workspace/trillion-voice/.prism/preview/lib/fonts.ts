import { Instrument_Serif, Inter, JetBrains_Mono } from "next/font/google";

export const fontDisplay = Instrument_Serif({ subsets: ["latin"], weight: ["400"], variable: "--font-display", display: "swap" });
export const fontBody = Inter({ subsets: ["latin"], variable: "--font-body", display: "swap" });
export const fontMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });
