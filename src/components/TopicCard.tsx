"use client";

import Link from "next/link";
import { Topic, scoreColour } from "../lib/api";
import ScoreGauge from "./ScoreGauge";

const DOMAIN_STYLES: Record<
    string,
    { bg: string; text: string; border: string }
> = {
    health: {
        bg: "rgba(244,63,94,0.08)",
        text: "#f87171",
        border: "rgba(244,63,94,0.2)",
    },
    economic: {
        bg: "rgba(251,146,60,0.08)",
        text: "#fdba74",
        border: "rgba(251,146,60,0.2)",
    },
    political: {
        bg: "rgba(167,139,250,0.08)",
        text: "#c4b5fd",
        border: "rgba(167,139,250,0.2)",
    },
    climate: {
        bg: "rgba(52,211,153,0.08)",
        text: "#6ee7b7",
        border: "rgba(52,211,153,0.2)",
    },
};

export default function TopicCard({
    topic,
    index = 0,
}: {
    topic: Topic;
    index?: number;
}) {
    const colour = scoreColour(topic.sanity_score);
    const ds = DOMAIN_STYLES[topic.data_domain] ?? {
        bg: "rgba(255,255,255,0.05)",
        text: "#a1a1aa",
        border: "rgba(255,255,255,0.1)",
    };

    return (
        <Link
            href={"/topic/" + topic.topic_id}
            style={{ textDecoration: "none", display: "block" }}
        >
            <div
                className={"anim-fadeup anim-delay-" + Math.min(index + 1, 5)}
                style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    padding: "20px 22px",
                    cursor: "pointer",
                    transition: "border-color 0.2s, background 0.2s",
                }}
                onMouseEnter={(e) => {
                    (e.currentTarget as HTMLDivElement).style.borderColor =
                        "var(--border2)";
                    (e.currentTarget as HTMLDivElement).style.background =
                        "var(--surface2)";
                }}
                onMouseLeave={(e) => {
                    (e.currentTarget as HTMLDivElement).style.borderColor =
                        "var(--border)";
                    (e.currentTarget as HTMLDivElement).style.background =
                        "var(--surface)";
                }}
            >
                <div
                    style={{
                        display: "flex",
                        gap: 18,
                        alignItems: "flex-start",
                    }}
                >
                    <ScoreGauge
                        score={topic.sanity_score}
                        size="md"
                        animated={false}
                    />

                    <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                marginBottom: 8,
                                flexWrap: "wrap",
                            }}
                        >
                            <span
                                style={{
                                    fontSize: 10,
                                    fontFamily: "DM Mono,monospace",
                                    letterSpacing: "0.1em",
                                    textTransform: "uppercase",
                                    padding: "2px 8px",
                                    borderRadius: 4,
                                    background: ds.bg,
                                    color: ds.text,
                                    border: "1px solid " + ds.border,
                                }}
                            >
                                {topic.data_domain}
                            </span>
                            {topic.low_confidence && (
                                <span
                                    style={{
                                        fontSize: 10,
                                        fontFamily: "DM Mono,monospace",
                                        letterSpacing: "0.08em",
                                        textTransform: "uppercase",
                                        padding: "2px 8px",
                                        borderRadius: 4,
                                        background: "rgba(234,179,8,0.08)",
                                        color: "#fbbf24",
                                        border: "1px solid rgba(234,179,8,0.2)",
                                    }}
                                >
                                    Low confidence
                                </span>
                            )}
                        </div>

                        <h2
                            style={{
                                fontSize: 14,
                                fontWeight: 500,
                                color: "var(--text)",
                                lineHeight: 1.4,
                                margin: "0 0 8px",
                                display: "-webkit-box",
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: "vertical",
                                overflow: "hidden",
                            }}
                        >
                            {topic.topic_title}
                        </h2>

                        <p
                            style={{
                                fontSize: 12,
                                color: "var(--muted)",
                                lineHeight: 1.5,
                                margin: "0 0 12px",
                                display: "-webkit-box",
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: "vertical",
                                overflow: "hidden",
                            }}
                        >
                            {topic.reason}
                        </p>

                        {/* Divergence bar */}
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                            }}
                        >
                            <span
                                style={{
                                    fontSize: 10,
                                    fontFamily: "DM Mono,monospace",
                                    color: "var(--muted)",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                Data
                            </span>
                            <div
                                style={{
                                    flex: 1,
                                    height: 2,
                                    background: "rgba(255,255,255,0.06)",
                                    borderRadius: 1,
                                    position: "relative",
                                    overflow: "hidden",
                                }}
                            >
                                <div
                                    style={{
                                        position: "absolute",
                                        left: 0,
                                        top: 0,
                                        height: "100%",
                                        width:
                                            topic.data_implied_score * 100 +
                                            "%",
                                        background: "#4ade80",
                                        borderRadius: 1,
                                    }}
                                />
                                <div
                                    style={{
                                        position: "absolute",
                                        top: 0,
                                        height: "100%",
                                        left:
                                            topic.data_implied_score * 100 +
                                            "%",
                                        width:
                                            Math.abs(topic.divergence_vector) *
                                                100 +
                                            "%",
                                        background: colour,
                                        opacity: 0.7,
                                        borderRadius: 1,
                                    }}
                                />
                            </div>
                            <span
                                style={{
                                    fontSize: 10,
                                    fontFamily: "DM Mono,monospace",
                                    color: "var(--muted)",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                Narrative
                            </span>
                        </div>

                        {topic.top_hype_keywords.length > 0 && (
                            <div
                                style={{
                                    display: "flex",
                                    flexWrap: "wrap",
                                    gap: 6,
                                    marginTop: 10,
                                }}
                            >
                                {topic.top_hype_keywords
                                    .slice(0, 4)
                                    .map((kw) => (
                                        <span
                                            key={kw}
                                            style={{
                                                fontSize: 10,
                                                fontFamily: "DM Mono,monospace",
                                                background:
                                                    "rgba(255,255,255,0.04)",
                                                color: "var(--text-sub)",
                                                border: "1px solid var(--border)",
                                                borderRadius: 3,
                                                padding: "2px 7px",
                                            }}
                                        >
                                            {kw}
                                        </span>
                                    ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </Link>
    );
}
