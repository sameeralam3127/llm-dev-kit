# syntax=docker/dockerfile:1

# --- base ---------------------------------------------------------------
# openssl is required by Prisma's query engine. Shared by every stage below
# so the apt install (and its network fetch of the package index) happens
# once per build instead of three times.
FROM node:22-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS base
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

# sqlite (default) or postgresql, for the v3 lite profile. `npm run build`
# regenerates the Prisma client from the switched schema, and the runtime stage
# copies that schema for `prisma db push`.
ARG DATABASE_PROVIDER=sqlite
RUN node prisma/use-provider.mjs "$DATABASE_PROVIDER"

# Config is validated at startup, but `next build` still evaluates it while
# prerendering the few static pages, so placeholders have to exist here.
#
# They are set inline on the RUN command rather than via ENV or ARG: that scopes
# them to this single command, so they never land in image metadata and no
# scanner can mistake them for real credentials. Compose injects the real values
# at runtime.
RUN DATABASE_URL="file:/tmp/build.db" \
    AUTH_SECRET="build-placeholder-not-a-real-credential" \
    npm run build

# --- runtime ----------------------------------------------------------------
FROM base AS runtime

RUN useradd --system --uid 1001 --create-home nextjs

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
# Standalone's server.js binds to $HOSTNAME, and Docker sets that to the
# container ID by default, so the server would listen there instead of on a
# reachable address -- the healthcheck (and nginx's upstream) probe
# 127.0.0.1 from inside the container, so both would fail to connect while
# the app was in fact running.
ENV HOSTNAME="0.0.0.0"

# Next's build-time tracing (`output: 'standalone'`) copies only the files the
# server actually requires, not the whole node_modules: ~900 MB down to the
# tens of MB below, including @prisma/client's generated query engine, which
# the tracer follows because the app imports it. `package.json` and
# `next.config.mjs` come along inside .next/standalone already.
COPY --chown=nextjs:nextjs --from=build /app/.next/standalone ./
COPY --chown=nextjs:nextjs --from=build /app/.next/static ./.next/static
COPY --chown=nextjs:nextjs --from=build /app/public ./public
COPY --chown=nextjs:nextjs --from=build /app/prisma ./prisma

# The Prisma CLI itself is not traced: `prisma db push` runs as a shell
# command at startup, never imported by server code, and it is a
# devDependency besides. Installed on its own, pinned to the version this
# image built the client with (read from package.json, which standalone
# output keeps a full copy of), rather than copying node_modules/prisma's
# own large and separately-versioned dependency tree.
RUN --mount=type=cache,target=/root/.npm \
    PRISMA_VERSION=$(node -p "require('./package.json').devDependencies.prisma") && \
    npm install --no-save --omit=dev --prefix /tmp/prisma-cli "prisma@$PRISMA_VERSION" && \
    cp -a /tmp/prisma-cli/node_modules/. node_modules/ && \
    rm -rf /tmp/prisma-cli && \
    chown -R nextjs:nextjs node_modules

# SQLite lives here; mount a volume so history survives container replacement.
# A plain (non -R) chown: ownership is set per file on each COPY above
# instead, since `chown -R` over content already in a lower image layer makes
# the overlay filesystem copy every file into a new layer just to relabel it,
# roughly doubling the image.
RUN mkdir -p /data && chown nextjs:nextjs /data
VOLUME /data

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --retries=10 --start-period=20s \
  CMD node -e "fetch('http://127.0.0.1:3000/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

# Push the schema on boot so a fresh volume is usable without a manual step.
# Duplicate message positions from older versions are renumbered first, or the
# push could not add their unique index. `server.js` is standalone's own
# entry point, the same server `next start` ran, reading the same PORT.
CMD ["sh", "-c", "node prisma/before-push.mjs && node node_modules/prisma/build/index.js db push --skip-generate && node server.js"]
