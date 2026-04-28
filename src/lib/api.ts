// Typed API client for the CrowdAudit backend
// All components import from here — never fetch directly in components.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface SignalBreakdown {
    S1_narrative_velocity: number;
    S2_hype_spike: number;
    S3_reality_divergence: number;
    weights: {
        S1_narrative_velocity: number;
        S2_hype_spike: number;
        S3_reality_divergence: number;
    };
}

export interface Topic {
    topic_id: string;
    topic_title: string;
    sanity_score: number; // 0–100
    irrationality_index: number; // 0.0–1.0
    signal_breakdown: SignalBreakdown;
    divergence_vector: number; // narrative_intensity − data_implied_score (signed)
    top_hype_keywords: string[];
    reason: string;
    low_confidence: boolean;
    adversarial_notes: string[];
    data_implied_score: number; // 0–1, what official data implies
    narrative_intensity: number; // 0–1, current public narrative intensity
    data_domain: "economic" | "health" | "political" | "climate";
    computed_at: string;
}

export interface RankedTopicsResponse {
    topics: Topic[];
    computed_at: string;
    total_topics: number;
}

// Score → colour mapping (matches Role A's documented thresholds)
export function scoreColour(score: number): string {
    if (score >= 80) return "#4ade80"; // green  — grounded
    if (score >= 60) return "#f0c040"; // yellow — mostly sound
    if (score >= 40) return "#f97316"; // orange — drifting
    return "#ef4444"; // red    — distorted / detached
}

export function scoreLabel(score: number): string {
    if (score >= 90) return "Grounded";
    if (score >= 70) return "Mostly sound";
    if (score >= 50) return "Drifting";
    if (score >= 30) return "Distorted";
    return "Detached";
}

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
    return res.json() as Promise<T>;
}

export const api = {
    health: () => get<{ status: string; version: string }>("/health"),

    rankedTopics: (params?: {
        limit?: number;
        min_irrationality?: number;
        data_domain?: string;
    }) => {
        const q = new URLSearchParams();
        if (params?.limit) q.set("limit", String(params.limit));
        if (params?.min_irrationality)
            q.set("min_irrationality", String(params.min_irrationality));
        if (params?.data_domain) q.set("data_domain", params.data_domain);
        const qs = q.toString();
        return get<RankedTopicsResponse>(
            `/v1/topics/ranked${qs ? `?${qs}` : ""}`
        );
    },

    topic: (topic_id: string) => get<Topic>(`/v1/sanity-score/${topic_id}`),
};
