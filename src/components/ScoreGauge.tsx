"use client";
import { useEffect, useRef } from "react";
import { scoreColour, scoreLabel } from "../lib/api";

interface Props {
    score: number;
    size?: "sm" | "md" | "lg";
    animated?: boolean;
}

export default function ScoreGauge({
    score,
    size = "lg",
    animated = true,
}: Props) {
    const colour = scoreColour(score);
    const label = scoreLabel(score);
    const arcRef = useRef<SVGCircleElement>(null);

    const dim = size === "lg" ? 160 : size === "md" ? 100 : 68;
    const sw = size === "lg" ? 10 : size === "md" ? 7 : 5;
    const r = (dim - sw * 2) / 2;
    const circ = 2 * Math.PI * r;
    const arcSpan = circ * 0.75;
    const target = (score / 100) * arcSpan;

    const numSize = size === "lg" ? 42 : size === "md" ? 26 : 18;
    const lblSize = size === "lg" ? 11 : size === "md" ? 9 : 8;

    useEffect(() => {
        if (!animated || !arcRef.current) return;
        const el = arcRef.current;
        el.style.strokeDasharray = "0 " + circ;
        const id = requestAnimationFrame(() => {
            el.style.transition =
                "stroke-dasharray 1s cubic-bezier(0.16,1,0.3,1)";
            el.style.strokeDasharray = target + " " + circ;
        });
        return () => cancelAnimationFrame(id);
    }, [score, target, circ, animated]);

    return (
        <div
            style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
            }}
        >
            <div style={{ position: "relative", width: dim, height: dim }}>
                {score < 30 && size === "lg" && (
                    <div
                        style={{
                            position: "absolute",
                            inset: sw,
                            borderRadius: "50%",
                            border: "2px solid " + colour,
                            animation: "pulse-ring 2s ease-out infinite",
                            opacity: 0.4,
                        }}
                    />
                )}
                <svg
                    width={dim}
                    height={dim}
                    style={{ transform: "rotate(135deg)", overflow: "visible" }}
                >
                    <circle
                        cx={dim / 2}
                        cy={dim / 2}
                        r={r}
                        fill="none"
                        stroke="rgba(255,255,255,0.06)"
                        strokeWidth={sw}
                        strokeDasharray={arcSpan + " " + circ}
                        strokeLinecap="round"
                    />
                    <circle
                        ref={arcRef}
                        cx={dim / 2}
                        cy={dim / 2}
                        r={r}
                        fill="none"
                        stroke={colour}
                        strokeWidth={sw}
                        strokeDasharray={
                            animated ? "0 " + circ : target + " " + circ
                        }
                        strokeLinecap="round"
                    />
                </svg>
                <div
                    style={{
                        position: "absolute",
                        inset: 0,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    <span
                        style={{
                            fontSize: numSize,
                            fontFamily: "Syne,sans-serif",
                            fontWeight: 800,
                            color: colour,
                            lineHeight: 1,
                            letterSpacing: "-0.03em",
                        }}
                    >
                        {score}
                    </span>
                    {size === "lg" && (
                        <span
                            style={{
                                fontSize: 9,
                                fontFamily: "DM Mono,monospace",
                                color: "var(--muted)",
                                letterSpacing: "0.1em",
                                textTransform: "uppercase",
                                marginTop: 4,
                            }}
                        >
                            / 100
                        </span>
                    )}
                </div>
            </div>
            <span
                style={{
                    fontSize: lblSize,
                    fontFamily: "DM Mono,monospace",
                    color: colour,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                }}
            >
                {label}
            </span>
        </div>
    );
}
