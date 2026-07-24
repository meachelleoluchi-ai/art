# Book Catalog API

A RESTful API for managing a catalog of books, built with Django and Django REST
Framework. The project is containerized with Docker, runs against PostgreSQL via
Docker Compose, and is built and published to GitHub Container Registry by a
GitHub Actions pipeline.

- **Framework:** Django 6.0.7 + Django REST Framework 3.17.1
- **Database:** SQLite (local default) / PostgreSQL 17.5 (Compose & production)
- **Container:** `python:3.13-slim`
- **CI/CD:** GitHub Actions → GHCR

---

## Project layout

```text
.
├── bookcatalog/            # Django project (settings, root URLconf, WSGI/ASGI)
│   ├── settings.py
│   └── urls.py
├── api/                    # The books app
│   ├── models.py           # Book model
│   ├── serializer.py       # BookSerializer
│   ├── views.py            # BookView, BookDetailView
│   ├── urls.py             # /api/books/ routes
│   ├── tests.py            # API test suite
│   └── migrations/
├── k8s/                    # Kubernetes manifests
├── .github/workflows/      # CI/CD pipeline
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── manage.py
```

---

## The Book model

| Field            | Type                    | Notes                          |
| ---------------- | ----------------------- | ------------------------------ |
| `id`             | `BigAutoField`          | Primary key, auto-generated    |
| `title`          | `CharField(255)`        | Required                       |
| `description`    | `TextField`             | Optional (`blank=True`)        |
| `author`         | `CharField(255)`        | Required                       |
| `isbn`           | `CharField(17)`         | Required, **unique**, normalised |
| `published_date` | `DateField`             | Required, `YYYY-MM-DD`         |
| `created_at`     | `DateTimeField`         | Set on insert, read-only       |
| `updated_at`     | `DateTimeField`         | Set on every save, read-only   |

Validation rules enforced by `BookSerializer`:

- **ISBN** — hyphens and spaces are stripped, then the value must be exactly 10
  or 13 digits. Normalisation happens *before* the uniqueness check, so
  `978-0-441-01359-3` and `9780441013593` are correctly recognised as the same
  book.
- **Published date** — a date in the future is rejected.
- **Title** — surrounding whitespace is trimmed and a blank title is rejected.

Each failure returns `400 Bad Request` with a per-field message.

---

## API reference

Base path: `/api/`

| Method   | Endpoint            | Description             | Success        |
| -------- | ------------------- | ----------------------- | -------------- |
| `GET`    | `/api/books/`       | List all books          | `200 OK`       |
| `POST`   | `/api/books/`       | Create a book           | `201 Created`  |
| `GET`    | `/api/books/{id}/`  | Retrieve a single book  | `200 OK`       |
| `PUT`    | `/api/books/{id}/`  | Replace a book          | `200 OK`       |
| `DELETE` | `/api/books/{id}/`  | Delete a book           | `204 No Content` |
| `GET`    | `/health/`          | Health probe — `{"status": "ok"}` | `200 OK` |

Error responses:

| Status              | When                                                |
| ------------------- | --------------------------------------------------- |
| `400 Bad Request`   | Validation failed — returns per-field error messages |
| `404 Not Found`     | No book with that `id` — returns `{"error": "Book not found"}` |

The Django admin is available at `/admin/`.

### Example requests

Create a book:

```bash
curl -X POST http://localhost:8000/api/books/ \
  -H "Content-Type: application/json" \
  -d '{
        "title": "Atomic Habits",
        "description": "A book about habits",
        "author": "James Clear",
        "isbn": "9780735211292",
        "published_date": "2018-01-01"
      }'
```

List all books:

```bash
curl http://localhost:8000/api/books/
```

Retrieve one book:

```bash
curl http://localhost:8000/api/books/1/
```

Update a book (`PUT` replaces the whole resource — send every field):

```bash
curl -X PUT http://localhost:8000/api/books/1/ \
  -H "Content-Type: application/json" \
  -d '{
        "title": "Atomic Habits (Revised)",
        "description": "Updated description",
        "author": "James Clear",
        "isbn": "9780735211292",
        "published_date": "2018-01-01"
      }'
```

Delete a book:

```bash
curl -X DELETE http://localhost:8000/api/books/1/
```

---

## Running locally

Requires Python 3.13.

```bash
git clone https://github.com/meachelleoluchi-ai/art.git
cd art

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

The API is now at <http://localhost:8000/api/books/>.

With no environment variables set, `DEVELOPMENT_MODE` defaults to `True` and the
app uses a local SQLite file (`db.sqlite3`) — no database server needed.

To create an admin user for `/admin/`:

```bash
python manage.py createsuperuser
```

---

## Configuration

All database configuration is read from environment variables in
[`bookcatalog/settings.py`](bookcatalog/settings.py):

| Variable            | Default | Purpose                                              |
| ------------------- | ------- | ---------------------------------------------------- |
| `DEVELOPMENT_MODE`  | `True`  | `True` → SQLite. `False` → PostgreSQL.               |
| `DATABASE_NAME`     | `""`    | PostgreSQL database name                             |
| `DATABASE_USER`     | `""`    | PostgreSQL user                                      |
| `DATABASE_PASSWORD` | `""`    | PostgreSQL password                                  |
| `DATABASE_HOST`     | `""`    | PostgreSQL host                                      |

The PostgreSQL port is fixed at `5432`.

---

## Running with Docker

### Docker Compose (app + PostgreSQL)

```bash
docker compose up --build
```

This builds the application image and starts it alongside a `postgres:17.5`
container. Compose sets `DEVELOPMENT_MODE=false`, so the app connects to
PostgreSQL rather than SQLite. Database files persist in the `pg_data` volume.

The API is exposed on <http://localhost:8000>.

Run migrations against the Compose database:

```bash
docker compose exec app python manage.py migrate
```

Tear down (add `-v` to also delete the database volume):

```bash
docker compose down
```

### Building the image directly

```bash
docker build -t book-catalog-api .
docker run -p 8000:8000 book-catalog-api
```

The image runs as the unprivileged `appuser`. On start,
[`entrypoint.sh`](entrypoint.sh) applies migrations and then launches gunicorn
(worker count configurable via `GUNICORN_WORKERS`, default 3). With no database
environment variables passed, the container falls back to SQLite inside the
container.

---

## Running the tests

15 tests in [`api/tests.py`](api/tests.py), all using DRF's `APITestCase` and
exercising the app end-to-end through the HTTP layer:

| Class | Covers |
| ----- | ------ |
| `BookAPITest` | The five CRUD endpoints plus the `404` path for a missing book |
| `BookValidationTest` | ISBN normalisation, length and digit rules, duplicate detection (including the hyphenated form), future dates, blank and padded titles |
| `HealthCheckTest` | `/health/` returns `200` with `{"status": "ok"}` |

Each test runs against a throwaway test database, created and destroyed by
Django automatically.

```bash
python manage.py test
```

To run a single test:

```bash
python manage.py test api.tests.BookAPITest.test_create_book
```

---

## CI/CD

The pipeline lives in
[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) and runs on every
push and pull request targeting `main`.

| Job | Depends on | What it does |
| --- | --- | --- |
| `test` | — | Runs the test suite |
| `runmigrations` | — | Applies migrations, proving they run cleanly |
| `migrations-check` | — | `makemigrations --check` — fails if a model change has no migration |
| `helm-lint` | — | `helm lint` plus a template render of the chart |
| `build-docker-image` | the four above | Builds with Buildx + GHA layer caching and pushes to GHCR |
| `deploy` | `build-docker-image` | `helm upgrade --install`, then verifies the rollout |

The four verification jobs run in parallel; the build job runs only if all of
them pass **and** the ref is `main`, so pull requests are fully validated but
never publish an image. Authentication to GHCR uses the built-in `GITHUB_TOKEN`,
so no long-lived registry credentials are stored in the repository. Images are
tagged with both the commit SHA and `latest`.

The deploy job reads cluster credentials from a base64-encoded `KUBE_CONFIG`
secret and injects the freshly-built image tag into the chart via `--set`. If
`KUBE_CONFIG` is absent the job logs a notice and skips the cluster steps rather
than failing, so the pipeline stays green on forks and before a cluster exists.

Deployment secrets are supplied at install time from the `DJANGO_SECRET_KEY` and
`DATABASE_PASSWORD` repository secrets.

---

## Kubernetes

### Helm (recommended)

The chart in [`charts/book-catalog/`](charts/book-catalog/) packages the whole
application as one parameterised release — Deployment, Service, Ingress,
ConfigMap, Secret, and an optional in-cluster PostgreSQL
(Deployment + Service + PersistentVolumeClaim).

```bash
helm upgrade --install book-catalog charts/book-catalog \
  --namespace book-catalog --create-namespace \
  --set image.tag=latest \
  --set secrets.secretKey="$(openssl rand -base64 48)" \
  --set secrets.databasePassword="$(openssl rand -base64 24)" \
  --wait
```

Notable chart behaviour:

- The app container gets all its configuration through `envFrom`, so the image
  itself carries no environment-specific data.
- A helper resolves the database host — the in-chart PostgreSQL Service by
  default, or an external host when `config.databaseHost` is set. Set
  `postgresql.enabled=false` when pointing at a managed database.
- The pod template is annotated with SHA-256 checksums of the ConfigMap and
  Secret, so a configuration change alters the pod template and triggers a
  rolling restart. Kubernetes does not do this on its own.
- Readiness and liveness probes hit `/health/`.

To disable the Ingress, set `ingress.enabled=false`. For TLS, set
`ingress.tls.enabled=true` and `ingress.tls.secretName`.

### Raw manifests

[`k8s/`](k8s/) holds the same objects as plain YAML, useful for inspecting them
without Helm:

```bash
kubectl apply -f k8s/
```

> The committed `k8s/secret.yaml` contains placeholder values. Replace it with a
> secret created out-of-band before using these manifests anywhere real.
