import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "CrowdAudit — Narrative vs Reality",
    description:
        "Detect when public narrative on a topic has drifted from what verified data actually says.",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body style={{ minHeight: "100vh" }}>
                <header
                    style={{
                        borderBottom: "1px solid var(--border)",
                        padding: "0 24px",
                        height: 52,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        position: "sticky",
                        top: 0,
                        background: "rgba(7,7,10,0.92)",
                        backdropFilter: "blur(12px)",
                        zIndex: 50,
                    }}
                >
                    <a
                        href="/"
                        style={{
                            textDecoration: "none",
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                        }}
                    >
                        <span
                            style={{
                                fontFamily: "Syne, sans-serif",
                                fontWeight: 800,
                                fontSize: 18,
                                color: "var(--text)",
                                letterSpacing: "-0.02em",
                            }}
                        >
                            Crowd
                            <span style={{ color: "var(--accent)" }}>
                                Audit
                            </span>
                        </span>
                    </a>
                    <span
                        style={{
                            fontFamily: "DM Mono, monospace",
                            fontSize: 10,
                            color: "var(--muted)",
                            letterSpacing: "0.12em",
                            textTransform: "uppercase",
                        }}
                    >
                        Narrative vs Reality
                    </span>
                </header>
                <main>{children}</main>
            </body>
        </html>
    );
}
