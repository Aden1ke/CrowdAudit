import { SignalBreakdown } from "@/lib/api";

const SIGNALS = [
    {
        key: "S1_narrative_velocity" as const,
        label: "Narrative velocity",
        colour: "#818cf8",
        desc: "Speed of Wikipedia narrative shift",
    },
    {
        key: "S2_hype_spike" as const,
        label: "Hype spike",
        colour: "#fb923c",
        desc: "Social & search volume anomaly",
    },
    {
        key: "S3_reality_divergence" as const,
        label: "Reality divergence",
        colour: "#f43f5e",
        desc: "Gap from official ground-truth data",
    },
];

export default function SignalBars({
    breakdown,
    showDesc = false,
}: {
    breakdown: SignalBreakdown;
    showDesc?: boolean;
}) {
    return (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {SIGNALS.map(({ key, label, colour, desc }) => {
                const val = breakdown[key];
                const pct = Math.round(val * 100);
                return (
                    <div key={key}>
                        <div
                            style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "baseline",
                                marginBottom: 6,
                            }}
                        >
                            <div>
                                <span
                                    style={{
                                        fontSize: 13,
                                        color: "var(--text-sub)",
                                    }}
                                >
                                    {label}
                                </span>
                                {showDesc && (
                                    <span
                                        style={{
                                            fontSize: 11,
                                            color: "var(--muted)",
                                            marginLeft: 8,
                                            fontFamily: "DM Mono,monospace",
                                        }}
                                    >
                                        {desc}
                                    </span>
                                )}
                            </div>
                            <span
                                style={{
                                    fontSize: 12,
                                    fontFamily: "DM Mono,monospace",
                                    color: colour,
                                    minWidth: 30,
                                    textAlign: "right",
                                }}
                            >
                                {pct}%
                            </span>
                        </div>
                        <div
                            style={{
                                height: 3,
                                background: "rgba(255,255,255,0.06)",
                                borderRadius: 2,
                                overflow: "hidden",
                            }}
                        >
                            <div
                                style={{
                                    height: "100%",
                                    width: pct + "%",
                                    background: colour,
                                    borderRadius: 2,
                                    transition:
                                        "width 0.8s cubic-bezier(0.16,1,0.3,1)",
                                }}
                            />
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
