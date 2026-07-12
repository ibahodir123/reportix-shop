# REPORTIX — Retail POS

Система учёта розничного магазина (каталог, склад, касса, отчёты). SaaS,
мультитенантность. Веб-платформа. Часть бренда REPORTIX.

Полный дизайн: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Стек

- **Backend:** Django 6 + DRF, PostgreSQL 16, Redis, django-rq
- **Frontend:** React 18 + TypeScript + Vite + Ant Design + Tailwind
- **Инфра:** Docker Compose

## Быстрый старт (dev)

```bash
cp .env.example .env            # при желании поправить пароли
docker compose up --build
```

Первый запуск сам применит миграции. Дальше:

```bash
# создать миграции (после изменения моделей)
docker compose exec backend python manage.py makemigrations

# суперпользователь для админки
docker compose exec backend python manage.py createsuperuser
```

- API health: http://localhost:8000/api/health/
- Django admin: http://localhost:8000/admin/
- Frontend: http://localhost:5173

> **Важно:** миграции приложений ещё не сгенерированы (в репозитории только
> пакеты `migrations/`). Первый `makemigrations` создаст их — выполнить один раз
> и закоммитить.

## Мультитенантность

Каждая доменная сущность наследует `apps.common.models.TenantOwnedModel`
(поле `tenant`). `TenantContextMiddleware` определяет текущий тенант по
членству пользователя; фронт передаёт выбранный бизнес заголовком
`X-Tenant-ID`. API-вьюсеты наследуют `TenantScopedViewSet` — изоляция данных.

## Структура

```
backend/  — Django API (apps: common, tenants, catalog, inventory)
frontend/ — React SPA (admin + позже POS)
docs/     — архитектура и решения
```

## Дальше по дорожной карте

1. `sales` — касса (смена, чек, оплата, возврат)
2. `voice` — голосовой ввод товаров (STT + NLU, ru/uz)
3. `purchasing`, `customers`, `reports`
```
