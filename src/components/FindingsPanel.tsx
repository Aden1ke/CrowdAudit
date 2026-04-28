"use client";
// Displays the three analytical findings from the Zerve canvas analysis

interface Insight {
    title: string;
    description: string;
    signal: string;
}

interface Findings {
    summary: string;
    key_finding: string;
    most_distorted: string;
    most_grounded: string;
    insights: Insight[];
    methodology: string;
    computed_at: string;
    zerve_canvas: string;
}

const SIGNAL_COLOURS: Record<string, string> = {
    S2_hype_spike: "#fb923c",
    S1_narrative_velocity: "#818cf8",
    S3_reality_divergence: "#f43f5e",
};

export default function FindingsPanel({ findings }: { findings: Findings }) {
    return (
        <div
            style={{
                background: "var(--surface, #0f0f14)",
                border: "1px solid rgba(255,255,255,0.07)",
                borderRadius: 14,
                padding: "24px 26px",
                marginBottom: 32,
            }}
        >
            {/* Header */}
            <div style={{ marginBottom: 20 }}>
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 10,
                        letterSpacing: "0.14em",
                        textTransform: "uppercase",
                        color: "#52525e",
                        margin: "0 0 8px",
                    }}
                >
                    Zerve Canvas Analysis ·{" "}
                    {new Date(findings.computed_at).toLocaleDateString()}
                </p>
                <p
                    style={{
                        fontSize: 13,
                        color: "#8888a0",
                        lineHeight: 1.65,
                        margin: 0,
                    }}
                >
                    {findings.key_finding}
                </p>
            </div>

            {/* Three insights */}
            <div
                style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                    marginBottom: 20,
                }}
            >
                {findings.insights.map((insight, i) => (
                    <div
                        key={i}
                        style={{
                            background: "rgba(255,255,255,0.02)",
                            border: `1px solid ${SIGNAL_COLOURS[insight.signal] || "rgba(255,255,255,0.07)"}33`,
                            borderLeft: `3px solid ${SIGNAL_COLOURS[insight.signal] || "#52525e"}`,
                            borderRadius: 8,
                            padding: "12px 16px",
                        }}
                    >
                        <p
                            style={{
                                fontFamily: "Syne,sans-serif",
                                fontWeight: 700,
                                fontSize: 13,
                                color: "#e8e8f0",
                                margin: "0 0 5px",
                            }}
                        >
                            {insight.title}
                        </p>
                        <p
                            style={{
                                fontSize: 12,
                                color: "#8888a0",
                                lineHeight: 1.6,
                                margin: 0,
                            }}
                        >
                            {insight.description}
                        </p>
                    </div>
                ))}
            </div>

            {/* Methodology footer */}
            <div
                style={{
                    borderTop: "1px solid rgba(255,255,255,0.06)",
                    paddingTop: 14,
                }}
            >
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 9,
                        color: "#52525e",
                        letterSpacing: "0.06em",
                        margin: "0 0 4px",
                    }}
                >
                    {findings.zerve_canvas}
                </p>
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 9,
                        color: "#52525e",
                        letterSpacing: "0.04em",
                        margin: 0,
                        lineHeight: 1.5,
                    }}
                >
                    {findings.methodology}
                </p>
            </div>
        </div>
    );
}
