# Localization audit (2026-10-20)

Interface text exists in English and Tamil. Strings live in typed locale modules (`frontend/src/lib/locales/*.ts`): each module declares `ta: Record<keyof typeof en, string>`, so a missing Tamil entry is a **compile error**. The Tamil is an **unreviewed translation written for this project**; it has not been checked by a professional translator.

## Rules

* Scheme and service names are always shown in both languages (selected language first, the other in brackets or on a second line).
* Department, category and district names come from the database's `name_ta` columns (`GET /api/v1/public/names`).
* API errors are translated from the HTTP status, never from the server's English text.
* Government-supplied prose without a Tamil version (eligibility lists, application steps, document names, complaint text, assistant answers when the model answers in English) is shown unchanged, marked `lang="en"`, with a visible notice in Tamil mode.
* Monospace text (identifiers, SQL, schema notation) and database values in the technical admin / Architecture views are not translated.
* Official document titles are never translated; no official Tamil title was published for the documents in the catalogue.

## Automated render audit

`frontend/audit/localization.js` renders every route/state in both languages and lists any visible text node, placeholder, aria-label, title, alt or option in the wrong language (rules in `frontend/audit/i18n-scan.js`). The same scanner runs in CI as `frontend/e2e/localization.spec.ts` (15 states x 2 languages plus detail pages).

* States rendered: **38** x 2 languages = 76 renders; renders with errors: 0.
* Issues found: Tamil **0**, English **0**.
* Missing-translation warnings logged by the app: 0.

| State | Role | Tamil issues | English issues |
|---|---|---|---|
| 404 | anonymous | 0 | 0 |
| Admin: Audit Logs | sysadmin | 0 | 0 |
| Admin: Complaints | sysadmin | 0 | 0 |
| Admin: Data Quality | sysadmin | 0 | 0 |
| Admin: Datasets | sysadmin | 0 | 0 |
| Admin: Department Performance | sysadmin | 0 | 0 |
| Admin: Knowledge Graph | sysadmin | 0 | 0 |
| Admin: Overview | sysadmin | 0 | 0 |
| Admin: SQL Workspace | sysadmin | 0 | 0 |
| Admin: Schema Explorer | sysadmin | 0 | 0 |
| Admin: Verification Queue | sysadmin | 0 | 0 |
| Advanced concepts | admin | 0 | 0 |
| Architecture | admin | 0 | 0 |
| Assistant | citizen | 0 | 0 |
| Citizen dashboard | citizen | 0 | 0 |
| Complaints (citizen) file | citizen | 0 | 0 |
| Complaints (signed out) | anonymous | 0 | 0 |
| Complaints mine | citizen | 0 | 0 |
| Complaints track | citizen | 0 | 0 |
| Department admin console | deptadmin | 0 | 0 |
| ER diagram | admin | 0 | 0 |
| Implementation | admin | 0 | 0 |
| Landing | anonymous | 0 | 0 |
| Login | anonymous | 0 | 0 |
| Officer console | officer | 0 | 0 |
| Officer detail | officer | 0 | 0 |
| Policy documents | anonymous | 0 | 0 |
| Policy documents (details open) | anonymous | 0 | 0 |
| Register | anonymous | 0 | 0 |
| Relational schema | admin | 0 | 0 |
| Scheme benefits | anonymous | 0 | 0 |
| Scheme detail | anonymous | 0 | 0 |
| Scheme documents | anonymous | 0 | 0 |
| Scheme eligibility | anonymous | 0 | 0 |
| Schemes filters | anonymous | 0 | 0 |
| Schemes list | anonymous | 0 | 0 |
| Service detail | anonymous | 0 | 0 |
| Services list | anonymous | 0 | 0 |

## Known limitations

* Long-form government text (see rules above) is English-only in Tamil mode.
* Policy-document summaries in Tamil are unreviewed translations, flagged in the interface.
* The assistant answers in the language the model produces; the interface labels the answer language when it differs from the selected one.
* The automated audit cannot judge translation quality; a Tamil-speaking reviewer should check the locale files before public release.