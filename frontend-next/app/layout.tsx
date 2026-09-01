import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jbmono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ARIS Beta — Always On Race Intelligence System",
  description:
    "F1 race strategy decision-support: classical decision support stitched with modern ML, not end-to-end black-box AI. Beta.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} h-full dark`} suppressHydrationWarning>
      <body className="min-h-full flex flex-col bg-carbon text-white antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
