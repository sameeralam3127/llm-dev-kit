---
name: add-feature
description: "Add a feature to the web/ chat app following its established hot-pluggable layering: Prisma schema → service → validated route → typed client → hook → component. Use when the user wants a new capability in the chat UI or API (e.g. tags, export, system-prompt editor, usage stats) and it should land consistently with the existing architecture."
---

# Add a feature to web/

Features land through the same six layers every time. The consistency is the
point: every phase of the roadmap plugs in the same way, so reading one
feature teaches you all of them.

```
prisma/schema.prisma      data shape (only if new data is stored)
        ↓
src/server/services/      business logic + EVERY ownership check
        ↓
src/app/api/…/route.ts    thin handler: parse → delegate → serialise
        ↓
src/lib/api-client.ts     typed client + query key
        ↓
src/hooks/                React Query hook (+ optimistic update if instant-feel)
        ↓
src/components/           UI, using existing ui/ primitives
```

## Rules that keep it pluggable

1. **Routes never touch the database.** If you are writing `db.` in a route
   handler, stop — it belongs in a service. Services take `userId` as their
   first argument and enforce ownership with `where: { userId }`, throwing
   `notFound()` rather than leaking existence.
2. **Validation lives in `src/lib/validations/`** as Zod schemas, shared by
   the route (parse) and exported as types for the client. Strings that are
   really unions (roles, colours) are narrowed in `server/mappers.ts`, never
   trusted raw from the DB.
3. **Wire types are DTOs, not Prisma rows.** Dates cross as ISO strings.
   Add a mapper in `server/mappers.ts` for any new model.
4. **Schema stays portable**: no enums, no `Json`, no scalar lists — the
   SQLite → Postgres switch must remain a one-word change.
5. **Errors are `ApiError`s** (`server/http.ts`); handlers are wrapped in
   `withErrorHandling`. Never let a raw exception shape reach the client.
6. **UI**: reuse `components/ui/` primitives; every interactive element is
   keyboard-reachable with an accessible name (`sr-only` label on icon
   buttons); loading states get a skeleton, not a spinner-only blank;
   destructive actions get an `AlertDialog` confirm.

## Workflow

1. State the feature in one sentence and name which layers it touches (not
   every feature needs all six — UI-only features skip the top three).
2. If schema changes: edit `prisma/schema.prisma`, run
   `npm run db:push`, add the mapper.
3. Implement bottom-up (service → route → client → hook → component), keeping
   each layer compiling before the next.
4. Verify: `npm run typecheck && npm run lint && npm run build`, then
   exercise the new route with curl (auth via the session cookie flow in
   `/smoke-test`) or the UI via `npm run dev`.
5. If the feature is user-visible, add it to `web/README.md`'s feature list.

## Reference implementations to copy from

- **Full stack, simple:** folders — `server/services/folder-service.ts`,
  `app/api/folders/`, `hooks/use-folders.ts`, `components/sidebar/`.
- **Optimistic update:** `useUpdateChat` in `hooks/use-chats.ts` (snapshot,
  patch, rollback on error, invalidate on settle).
- **Streaming/complex:** the chat turn — `server/services/chat-service.ts`
  (`prepareTurn`) + `app/api/chat/route.ts` + `hooks/use-chat-stream.ts`.
