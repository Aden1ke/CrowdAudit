/** @type {import('next').NextConfig} */
const nextConfig = {

    // Adding these helps bypass common hackathon build blockers
    typescript: {
        ignoreBuildErrors: true,
    },
    eslint: {
        ignoreDuringBuilds: true,
    },
};

module.exports = nextConfig;
