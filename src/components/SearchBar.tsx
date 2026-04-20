"use client";
import { useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function SearchBar() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [value, setValue] = useState(searchParams.get("q") ?? "");
    const [, startTransition] = useTransition();

    function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
        const q = e.target.value;
        setValue(q);

        // Debounce — only update URL after 300ms of no typing
        startTransition(() => {
            const params = new URLSearchParams(searchParams.toString());
            if (q) params.set("q", q);
            else params.delete("q");
            router.replace("/?" + params.toString());
        });
    }

    return (
        <div
            style={{
                flex: 1,
                minWidth: 200,
                display: "flex",
                alignItems: "center",
                gap: 8,
                background: "#0f0f14",
                border: "1px solid rgba(255,255,255,0.12)",
                borderRadius: 8,
                padding: "0 12px",
                height: 34,
            }}
        >
            {/* Search icon */}
            <svg
                width="13"
                height="13"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                style={{ opacity: 0.35, flexShrink: 0, color: "#e8e8f0" }}
            >
                <circle cx="6.5" cy="6.5" r="4.5" />
                <path d="M10.5 10.5L14 14" strokeLinecap="round" />
            </svg>

            <input
                type="search"
                value={value}
                onChange={handleChange}
                placeholder="Search topics…"
                style={{
                    background: "none",
                    border: "none",
                    outline: "none",
                    fontFamily: "DM Sans, sans-serif",
                    fontSize: 12,
                    color: "#e8e8f0",
                    width: "100%",
                }}
            />

            {value && (
                <button
                    onClick={() => {
                        setValue("");
                        router.replace(
                            "/" +
                                (searchParams.get("domain")
                                    ? "?domain=" + searchParams.get("domain")
                                    : "")
                        );
                    }}
                    style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "#52525e",
                        fontSize: 14,
                        lineHeight: 1,
                        padding: 0,
                    }}
                >
                    ×
                </button>
            )}
        </div>
    );
}
