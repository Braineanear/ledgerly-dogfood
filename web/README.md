# Ledgerly web

This directory contains the Ledgerly web application scaffold. It is a
pnpm-managed Vite, React, and TypeScript project with no backend integration
or product workflows yet.

## Set up

From the repository root, install the locked dependencies:

```sh
pnpm --dir web install --frozen-lockfile
```

## Commands

Run these commands from the repository root:

```sh
pnpm --dir web dev
pnpm --dir web lint
pnpm --dir web test
pnpm --dir web build
```

`make web-dev` starts the development server. The root `make test`, `make
lint`, and `make build` targets include the corresponding web commands.
