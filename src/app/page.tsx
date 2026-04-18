import { Suspense } from "react";
import { api } from "@/lib/api";
import TopicCard from "@/components/TopicCard";
import SearchBar from "@/components/SearchBar";

const DOMAINS = [
    { value: "", label: "All topics" },
    { value: "health", label: "Health" },
    { value: "economic", label: "Economic" },
    { value: "political", label: "Political" },
    { value: "climate", label: "Climate" },
];

export default async function HomePage({
    searchParams,
}: {
    searchParams: { domain?: string; min?: string; q?: string };
}) {
    const domain = searchParams.domain ?? "";
    const min = parseFloat(searchParams.min ?? "0") || 0;
    const query = (searchParams.q ?? "").toLowerCase().trim();

    let data;
    let error: string | null = null;

    try {
        data = await api.rankedTopics({
            limit: 50,
            min_irrationality: min,
            data_domain: domain || undefined,
        });
    } catch {
        error =
            "Cannot reach the CrowdAudit API. Make sure the backend is running on port 8000.";
    }

    // Client-side search filter applied on the server-fetched list
    const topics = data
        ? data.topics.filter(
              (t) =>
                  !query ||
                  t.topic_title.toLowerCase().includes(query) ||
                  t.top_hype_keywords.some((k) =>
                      k.toLowerCase().includes(query)
                  ) ||
                  t.data_domain.toLowerCase().includes(query)
          )
        : [];

    return (
        <div
            style={{
                maxWidth: 760,
                margin: "0 auto",
                padding: "48px 20px 80px",
            }}
        >
            {/* Hero */}
            <div style={{ marginBottom: 40 }}>
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 10,
                        letterSpacing: "0.18em",
                        textTransform: "uppercase",
                        color: "#52525e",
                        marginBottom: 14,
                    }}
                >
                    ZerveHack 2026
                </p>
                <h1
                    style={{
                        fontFamily: "Syne,sans-serif",
                        fontWeight: 800,
                        fontSize: "clamp(36px,6vw,56px)",
                        lineHeight: 1,
                        letterSpacing: "-0.03em",
                        color: "#e8e8f0",
                        margin: "0 0 14px",
                    }}
                >
                    Crowd<span style={{ color: "#e8c547" }}>Audit</span>
                </h1>
                <p
                    style={{
                        fontSize: 15,
                        color: "#8888a0",
                        maxWidth: 480,
                        lineHeight: 1.7,
                        margin: 0,
                    }}
                >
                    Detecting when public narrative has drifted from what
                    verified data actually says — across health, economics,
                    politics, and climate.
                </p>
            </div>

            {/* Stats row */}
            {data && (
                <div
                    style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3,1fr)",
                        gap: 10,
                        marginBottom: 36,
                    }}
                >
                    {[
                        {
                            label: "Topics tracked",
                            value: data.total_topics,
                            colour: "#e8e8f0",
                        },
                        {
                            label: "Distorted+",
                            value: data.topics.filter(
                                (t) => t.sanity_score < 50
                            ).length,
                            colour: "#ef4444",
                        },
                        {
                            label: "Low confidence",
                            value: data.topics.filter((t) => t.low_confidence)
                                .length,
                            colour: "#fbbf24",
                        },
                    ].map(({ label, value, colour }) => (
                        <div
                            key={label}
                            style={{
                                background: "#0f0f14",
                                border: "1px solid rgba(255,255,255,0.07)",
                                borderRadius: 10,
                                padding: "14px 16px",
                            }}
                        >
                            <p
                                style={{
                                    fontFamily: "DM Mono,monospace",
                                    fontSize: 9,
                                    letterSpacing: "0.1em",
                                    textTransform: "uppercase",
                                    color: "#52525e",
                                    margin: "0 0 6px",
                                }}
                            >
                                {label}
                            </p>
                            <p
                                style={{
                                    fontFamily: "Syne,sans-serif",
                                    fontWeight: 800,
                                    fontSize: 26,
                                    color: colour,
                                    margin: 0,
                                    lineHeight: 1,
                                }}
                            >
                                {value}
                            </p>
                        </div>
                    ))}
                </div>
            )}

            {/* Search + filters */}
            <div
                style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 8,
                    marginBottom: 24,
                    alignItems: "center",
                }}
            >
                <Suspense>
                    <SearchBar />
                </Suspense>

                <form style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {DOMAINS.map(({ value, label }) => (
                        <button
                            key={value}
                            type="submit"
                            name="domain"
                            value={value}
                            style={{
                                fontFamily: "DM Mono,monospace",
                                fontSize: 10,
                                letterSpacing: "0.06em",
                                padding: "5px 13px",
                                borderRadius: 20,
                                cursor: "pointer",
                                transition: "all 0.15s",
                                border:
                                    domain === value
                                        ? "1px solid #e8c547"
                                        : "1px solid rgba(255,255,255,0.07)",
                                background:
                                    domain === value
                                        ? "rgba(232,197,71,0.08)"
                                        : "transparent",
                                color: domain === value ? "#e8c547" : "#52525e",
                            }}
                        >
                            {label}
                        </button>
                    ))}
                </form>
            </div>

            {/* Error */}
            {error && (
                <div
                    style={{
                        background: "rgba(239,68,68,0.07)",
                        border: "1px solid rgba(239,68,68,0.2)",
                        borderRadius: 10,
                        padding: "14px 18px",
                        marginBottom: 20,
                    }}
                >
                    <p
                        style={{
                            fontFamily: "DM Mono,monospace",
                            fontSize: 10,
                            letterSpacing: "0.08em",
                            textTransform: "uppercase",
                            color: "#f87171",
                            marginBottom: 4,
                        }}
                    >
                        API unreachable
                    </p>
                    <p
                        style={{
                            fontSize: 12,
                            color: "rgba(248,113,113,0.65)",
                            margin: 0,
                        }}
                    >
                        {error}
                    </p>
                </div>
            )}

            {/* Results meta */}
            {data && (
                <p
                    style={{
                        fontFamily: "DM Mono,monospace",
                        fontSize: 9,
                        color: "#52525e",
                        letterSpacing: "0.06em",
                        marginBottom: 14,
                    }}
                >
                    {topics.length} topic{topics.length !== 1 ? "s" : ""}
                    {query ? ` matching "${searchParams.q}"` : ""}
                    {domain ? " · " + domain : ""}
                    {" · "}updated{" "}
                    {new Date(data.computed_at).toLocaleTimeString()}
                </p>
            )}

            {/* Topic list */}
            {data && topics.length === 0 && (
                <p
                    style={{
                        color: "#52525e",
                        fontSize: 13,
                        fontFamily: "DM Mono,monospace",
                    }}
                >
                    {query
                        ? `No topics match "${searchParams.q}".`
                        : "No topics match the current filters."}
                </p>
            )}

            {data && topics.length > 0 && (
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                    }}
                >
                    {topics.map((topic, i) => (
                        <TopicCard
                            key={topic.topic_id}
                            topic={topic}
                            index={i}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
