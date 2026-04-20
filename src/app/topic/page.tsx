import { notFound } from "next/navigation";
import Link from "next/link";
import { api, scoreColour } from "@/lib/api";
import ScoreGauge from "@/components/ScoreGauge";
import SignalBars from "@/components/SignalBars";

const DOMAIN_LABEL: Record<string, string> = {
    health: "Health",
    economic: "Economics",
    political: "Politics",
    climate: "Climate",
};

export default async function TopicPage({
    params,
}: {
    params: { topic_id: string };
}) {
    let topic;
    try {
        topic = await api.topic(params.topic_id);
    } catch {
        notFound();
    }

    const colour = scoreColour(topic.sanity_score);
    const narrativePct = Math.round(topic.narrative_intensity * 100);
    const dataPct = Math.round(topic.data_implied_score * 100);
    const gapPct = Math.round(Math.abs(topic.divergence_vector) * 100);

    return (
        <div
            style={{
                maxWidth: 700,
                margin: "0 auto",
                padding: "40px 20px 80px",
            }}
        >
            <Link
                href="/"
                style={{
                    fontFamily: "DM Mono,monospace",
                    fontSize: 11,
                    color: "var(--muted)",
                    textDecoration: "none",
                    letterSpacing: "0.06em",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 32,
                }}
            >
                ← All topics
            </Link>

            {/* Title block */}
            <div className="anim-fadeup" style={{ marginBottom: 36 }}>
                <span
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 10,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                        color: "var(--muted)",
                        border: "1px solid var(--border)",
                        borderRadius: 4,
                        padding: "3px 10px",
                        display: "inline-block",
                        marginBottom: 14,
                    }}
                >
                    {DOMAIN_LABEL[topic.data_domain] ?? topic.data_domain}
                </span>
                <h1
                    style={{
                        fontFamily: "Syne,sans-serif",
                        fontWeight: 800,
                        fontSize: "clamp(22px,4vw,32px)",
                        lineHeight: 1.2,
                        letterSpacing: "-0.02em",
                        color: "var(--text)",
                        margin: 0,
                    }}
                >
                    {topic.topic_title}
                </h1>
            </div>

            {/* Score hero */}
            <div
                className="anim-fadeup anim-delay-1"
                style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 14,
                    padding: 28,
                    display: "flex",
                    gap: 32,
                    alignItems: "center",
                    flexWrap: "wrap",
                    marginBottom: 16,
                }}
            >
                <ScoreGauge score={topic.sanity_score} size="lg" animated />
                <div style={{ flex: 1, minWidth: 220 }}>
                    <p
                        style={{
                            fontFamily: "DM Mono,monospace",
                            fontSize: 10,
                            letterSpacing: "0.12em",
                            textTransform: "uppercase",
                            color: "var(--muted)",
                            marginBottom: 16,
                        }}
                    >
                        Signal breakdown
                    </p>
                    <SignalBars breakdown={topic.signal_breakdown} showDesc />
                </div>
            </div>

            {/* Why this score */}
            <div
                className="anim-fadeup anim-delay-2"
                style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    padding: "18px 22px",
                    marginBottom: 16,
                }}
            >
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 10,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                        color: "var(--muted)",
                        marginBottom: 10,
                    }}
                >
                    Why this score
                </p>
                <p
                    style={{
                        fontSize: 14,
                        color: "var(--text-sub)",
                        lineHeight: 1.7,
                        margin: 0,
                    }}
                >
                    {topic.reason}
                </p>
            </div>

            {/* Narrative vs reality */}
            <div
                className="anim-fadeup anim-delay-3"
                style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    padding: "18px 22px",
                    marginBottom: 16,
                }}
            >
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 10,
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                        color: "var(--muted)",
                        marginBottom: 18,
                    }}
                >
                    Narrative vs reality
                </p>

                {[
                    {
                        label: "Public narrative intensity",
                        value: topic.narrative_intensity,
                        pct: narrativePct,
                        colour,
                    },
                    {
                        label: "Data-implied level",
                        value: topic.data_implied_score,
                        pct: dataPct,
                        colour: "#4ade80",
                    },
                ].map(({ label, pct, colour: c }) => (
                    <div key={label} style={{ marginBottom: 14 }}>
                        <div
                            style={{
                                display: "flex",
                                justifyContent: "space-between",
                                marginBottom: 6,
                            }}
                        >
                            <span
                                style={{
                                    fontSize: 13,
                                    color: "var(--text-sub)",
                                }}
                            >
                                {label}
                            </span>
                            <span
                                style={{
                                    fontFamily: "DM Mono,monospace",
                                    fontSize: 12,
                                    color: c,
                                }}
                            >
                                {pct}%
                            </span>
                        </div>
                        <div
                            style={{
                                height: 4,
                                background: "rgba(255,255,255,0.06)",
                                borderRadius: 2,
                            }}
                        >
                            <div
                                style={{
                                    height: "100%",
                                    width: pct + "%",
                                    background: c,
                                    borderRadius: 2,
                                    transition:
                                        "width 0.8s cubic-bezier(0.16,1,0.3,1)",
                                }}
                            />
                        </div>
                    </div>
                ))}

                <div
                    style={{
                        marginTop: 12,
                        padding: "10px 14px",
                        background: "rgba(255,255,255,0.02)",
                        borderRadius: 8,
                        border: "1px solid var(--border)",
                    }}
                >
                    <span
                        style={{
                            fontFamily: "DM Mono,monospace",
                            fontSize: 11,
                            color: "var(--muted)",
                        }}
                    >
                        Gap:{" "}
                        <span style={{ color: colour }}>
                            {topic.divergence_vector > 0 ? "+" : ""}
                            {gapPct} percentage points
                        </span>
                        {" — "}narrative is{" "}
                        {topic.divergence_vector > 0
                            ? "more intense"
                            : "less intense"}{" "}
                        than data implies
                    </span>
                </div>
            </div>

            {/* Keywords */}
            {topic.top_hype_keywords.length > 0 && (
                <div
                    className="anim-fadeup anim-delay-4"
                    style={{
                        background: "var(--surface)",
                        border: "1px solid var(--border)",
                        borderRadius: 12,
                        padding: "18px 22px",
                        marginBottom: 16,
                    }}
                >
                    <p
                        style={{
                            fontFamily: "DM Mono,monospace",
                            fontSize: 10,
                            letterSpacing: "0.12em",
                            textTransform: "uppercase",
                            color: "var(--muted)",
                            marginBottom: 12,
                        }}
                    >
                        Hype keywords
                    </p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        {topic.top_hype_keywords.map((kw) => (
                            <span
                                key={kw}
                                style={{
                                    fontFamily: "DM Mono,monospace",
                                    fontSize: 12,
                                    background: "rgba(255,255,255,0.04)",
                                    color: "var(--text-sub)",
                                    border: "1px solid var(--border)",
                                    borderRadius: 4,
                                    padding: "5px 12px",
                                }}
                            >
                                {kw}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Low confidence panel */}
            {topic.low_confidence && topic.adversarial_notes.length > 0 && (
                <div
                    className="anim-fadeup anim-delay-5"
                    style={{
                        background: "rgba(234,179,8,0.05)",
                        border: "1px solid rgba(234,179,8,0.2)",
                        borderRadius: 12,
                        padding: "18px 22px",
                        marginBottom: 16,
                    }}
                >
                    <p
                        style={{
                            fontFamily: "DM Mono,monospace",
                            fontSize: 10,
                            letterSpacing: "0.12em",
                            textTransform: "uppercase",
                            color: "#fbbf24",
                            marginBottom: 12,
                        }}
                    >
                        Low confidence — counter-narratives identified
                    </p>
                    <ul
                        style={{
                            listStyle: "none",
                            padding: 0,
                            margin: 0,
                            display: "flex",
                            flexDirection: "column",
                            gap: 8,
                        }}
                    >
                        {topic.adversarial_notes.map((note, i) => (
                            <li
                                key={i}
                                style={{
                                    fontSize: 13,
                                    color: "rgba(251,191,36,0.6)",
                                    lineHeight: 1.65,
                                    paddingLeft: 14,
                                    position: "relative",
                                }}
                            >
                                <span
                                    style={{
                                        position: "absolute",
                                        left: 0,
                                        color: "#fbbf24",
                                    }}
                                >
                                    —
                                </span>
                                {note}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            <p
                style={{
                    fontFamily: "DM Mono,monospace",
                    fontSize: 10,
                    color: "var(--muted)",
                    marginTop: 32,
                }}
            >
                Computed {new Date(topic.computed_at).toUTCString()}
            </p>
        </div>
    );
}
