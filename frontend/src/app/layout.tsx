import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BTC Trading Terminal",
  description: "Real-time BTC trading dashboard with technical analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased overflow-hidden">
        {children}
      </body>
    </html>
  );
}
