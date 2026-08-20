# The frontend as the local daily driver (Phase B3-local).
#
# A BUILT bundle behind nginx, not `vite dev`. That is the point of this stack:
# the thing you open every day should be the built artifact, started by one
# command, while hot-reload development stays native on the host at :5173.
#
# node:24-alpine matches the host toolchain (v24.14.0) — a build image behind the
# host's Node can resolve a different dependency tree than the one `npm run build`
# proves locally, which turns "works on my machine" into a container-only bug.

FROM node:24-alpine AS build

WORKDIR /src

# Lockfile-exact install, cached until the manifests actually change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite inlines env at BUILD time, so these must be build args rather than runtime
# environment — setting them in compose's `environment:` would silently do
# nothing and the bundle would fall back to its localhost:8000 default, i.e. the
# dev API rather than this stack's.
ARG VITE_API_URL
ARG VITE_DEBUG
ENV VITE_API_URL=$VITE_API_URL \
    VITE_DEBUG=$VITE_DEBUG

RUN npm run build


FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
# Included by BOTH server blocks in nginx.conf (:80 open, :8080 Basic-auth), so
# the bundle and the /_api proxy are defined exactly once.
COPY nginx-common.conf /etc/nginx/snippets/app-common.conf
COPY --from=build /src/dist /usr/share/nginx/html

EXPOSE 80

# 127.0.0.1, NOT localhost — and this is not a style preference. nginx below
# binds IPv4 only (`listen 80;`), while musl's resolver tries ::1 first for
# `localhost`, so the check got "Connection refused" while the site served fine
# to the host. It failed 1350 times in a row before anyone read it (2026-08-12).
#
# The fix belongs here rather than in nginx.conf: this container has no IPv6
# stack at all (netstat shows no ::-bound socket), so adding `listen [::]:80;`
# would make nginx fail to bind and refuse to START — turning a cosmetic false
# alarm into a real outage.
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
