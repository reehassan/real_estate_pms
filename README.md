# Royalland PMS — Real Estate Property Management System

A production-grade Property Management System built for **Royalland Developers**, a Pakistani real estate client managing multiple housing scheme projects, plot inventories, customer bookings, installment schedules, and project expenses.

This system replaced a spreadsheet-based workflow for the client and has been in active use since 2026. The live client deployment runs on a separate, privately-hosted instance — this repository and the demo below are a portfolio-facing replica for evaluation purposes, seeded with sample data rather than real client records.

## Status

**In production for the client** (private deployment) · **Demo available below** for evaluation.

## Demo

Live demo: http://141.145.158.16

```
username: admin
password: admin123
```

> Seeded with sample data — this is a separate deployment from the client's live system, safe to explore and reset.

## What it does

- **Full sales lifecycle modeling** — Projects, Units, Customers, Bookings, Installment Plans, Installments, Payments, and Expenses
- **Automated challan generation** — payment challan PDFs generated on demand via WeasyPrint, replacing a manual documentation step for client staff
- **Overdue detection** — scheduled management commands (cron-based) flag overdue installments automatically, no manual tracking required
- **Financial integrity** — append-only audit logging on financial records, soft-delete instead of hard-delete, role-based admin access via django-unfold
- **Self-managed deployment** — owned end-to-end: architecture, deployment, and ongoing maintenance on a self-managed Linux VPS

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Django, Django ORM |
| Frontend | HTMX, Tailwind CSS |
| Database | PostgreSQL |
| Documents | WeasyPrint (PDF generation) |
| Storage | Cloudflare R2 |
| Infra | Gunicorn, Nginx, Linux VPS |
| Scheduling | Cron + Django management commands |

## Why these choices

- **HTMX over a JS framework**: the client's team is small and the UI needs are form-heavy, not app-like — HTMX kept the stack simple without sacrificing interactivity.
- **Cron over Celery**: V1 scope didn't need a task queue; overdue detection and PDF generation run fine as scheduled management commands. Celery is scoped for V2 if async job volume grows.
- **Append-only audit log + soft delete**: this is a system of record for money. Nothing gets silently overwritten or deleted.

## Development notes

Built as my first production Django project, learned on a real client engagement rather than a tutorial. Dev logs and architecture notes are being written up as part of an ongoing portfolio series — see linked posts for the build process, including the mistakes.

## License

See [LICENSE](./LICENSE).
