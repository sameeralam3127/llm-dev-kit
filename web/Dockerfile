# syntax=docker/dockerfile:1

# --- base ---------------------------------------------------------------
# openssl is required by Prisma's query engine. Shared by every stage below
# so the apt install (and its network fetch of the package index) happens
# once per build instead of three times.
FROM node:20-slim AS base
WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update \
 && apt-get install -y --no-install-recommends openssl ca-certificates

# --- deps -----------------------------------------------------------------
FROM base AS deps

COPY package.json package-lock.json ./
COPY prisma ./prisma
# `npm ci` runs the postinstall (prisma generate), which needs the schema above.
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# --- build ------------------------------------------------------------------
FROM base AS build

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

# Config is validated at startup, but `next build` still evaluates it while
# prerendering the few static pages, so placeholders have to exist here.
#
# They are set inline on the RUN command rather than via ENV or ARG: that scopes
# them to this single command, so they never land in image metadata and no
# scanner can mistake them for real credentials. Compose injects the real values
# at runtime.
RUN DATABASE_URL="file:/tmp/build.db" \
    AUTH_SECRET="build-placeholder-not-a-real-credential" \
    npm run build \
 && npm prune --omit=dev

# --- runtime ----------------------------------------------------------------
FROM base AS runtime

RUN useradd --system --uid 1001 --create-home nextjs

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/prisma ./prisma

# SQLite lives here; mount a volume so history survives container replacement.
RUN mkdir -p /data && chown -R nextjs:nextjs /data /app
VOLUME /data

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=20s \
  CMD node -e "fetch('http://127.0.0.1:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# Push the schema on boot so a fresh volume is usable without a manual step.
CMD ["sh", "-c", "npx prisma db push --skip-generate && npm run start"]
