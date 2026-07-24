# Book Catalog API — Engineering Report

**Design, Build, Containerize & Deploy**

| | |
| --- | --- |
| **Author** | *(add your full name)* — GitHub `meachelleoluchi-ai` |
| **Repository** | <https://github.com/meachelleoluchi-ai/art> |
| **Date** | July 2026 |
| **Stack** | Django REST Framework · Docker · GitHub Actions · Kubernetes |

---

## 1. Introduction & Objectives

This report documents the design and implementation of the **Book Catalog API** —
a RESTful service for managing a collection of books — together with the
containerization and continuous-integration work that surrounds it.

The objective was not only to build a working API, but to practise a modern
software-delivery lifecycle: version control, automated tests, a container image,
an automated pipeline, and deployment manifests for Kubernetes.

### Status against the brief

| Requirement | Status | Detail |
| --- | --- | --- |
| REST API with CRUD for books | ✅ Done | Two DRF `APIView` classes covering list, create, retrieve, update, delete |
| Book model (title, author, ISBN, published date) | ✅ Done | Plus an optional `description` and audit timestamps; `isbn` is unique |
| Data validation with serializers | ✅ Done | ISBN normalisation and format, future-date and title rules |
| Unit tests (minimum 3) | ✅ Done | 15 tests, all passing |
| Git + GitHub | ✅ Done | Incremental history, feature branch merged via PR #1 |
| CI/CD (install → test → build → push → deploy) | ✅ Done | Six-job gated pipeline ending in a Helm deploy |
| Dockerfile + docker-compose | ✅ Done | Hardened app image plus a local PostgreSQL stack |
| Kubernetes manifests | ✅ Done | Deployment, Service, Ingress, ConfigMap, Secret, PostgreSQL |
| Helm chart | ✅ Done | All objects, with an optional in-cluster database |
| README + report | ✅ Done | This report and a full README |

Section 8 lists the improvements that remain open.

---

## 2. End-to-End Workflow

The project was built incrementally — each layer was made to work and committed
before the next was added, so the repository history reads as a clean
progression:

1. **Scaffold** — a Django project (`bookcatalog/`) with environment-driven
   database settings, so the same code runs locally and in containers.
2. **API** — the `api` app: the `Book` model, `BookSerializer`, and the
   `BookView` / `BookDetailView` views wired into `/api/`.
3. **Tests** — a suite exercising every endpoint through the HTTP layer.
4. **Containerization** — a `Dockerfile` and a `docker-compose.yml` that runs
   the app against real PostgreSQL.
5. **CI/CD** — a GitHub Actions workflow tying testing and image publishing
   together.
6. **Kubernetes** — manifests for a Deployment, Service and Ingress.

> **Design principle — configuration by environment.**
> The database connection is read from environment variables with safe local
> defaults. When `DEVELOPMENT_MODE` is `false` the app uses PostgreSQL;
> otherwise it falls back to SQLite. This single decision is what lets one
> codebase move between a laptop, Docker Compose and a cluster without a code
> change — and it keeps the test suite fast, because CI needs no external
> database.

### The API layer

The `Book` model stores `title`, an optional `description`, `author`, a **unique**
`isbn` (max 17 characters, leaving room for hyphenated ISBN-13), a
`published_date`, and automatic `created_at` / `updated_at` timestamps.

A dedicated `/health/` endpoint returns `{"status": "ok"}`. It deliberately does
not touch the database, so it stays a cheap target for Kubernetes liveness and
readiness probes.

CRUD is split across two views, which is what maps cleanly onto REST's
collection/resource distinction:

- **`BookView`** handles the collection at `/api/books/` — `GET` lists all books,
  `POST` creates one and returns `201 Created`.
- **`BookDetailView`** handles a single resource at `/api/books/{id}/` — `GET`,
  `PUT` and `DELETE`. Each method looks the book up first and returns a
  `404 Not Found` with a clear `{"error": "Book not found"}` body if it is
  absent, rather than raising an unhandled exception.

Validation lives in `BookSerializer`, where it produces clear `400` responses
close to the API boundary:

- **ISBN** — hyphens and spaces are stripped, then the value must be exactly 10
  or 13 digits.
- **Published date** — a date in the future is rejected.
- **Title** — whitespace is trimmed and a blank title is rejected.
- **Uniqueness** — DRF adds a validator automatically from the model's
  `unique=True`, so a duplicate ISBN is a `400` rather than a database integrity
  error.

The ordering of those last two rules is the subtle part. DRF runs a field's
validators *before* its `validate_<field>` hook, so normalising the ISBN inside
`validate_isbn` would be too late — the uniqueness check would already have
compared the raw hyphenated string against the compact stored form, found no
match, and let the duplicate through to fail at the database. Normalisation
therefore happens in `to_internal_value`, before field validation runs, so
`978-0-441-01359-3` and `9780441013593` are correctly recognised as the same
book. A test covers exactly this case.

**Why `APIView` rather than `ModelViewSet`:** a viewset would have produced the
same five endpoints in fewer lines, but writing the methods explicitly makes the
request/response cycle and each status code visible in the source. For a project
whose purpose is to demonstrate understanding, that legibility was worth the
extra lines. A viewset would be the better choice as the surface grows.

---

## 3. How the Docker Image Is Built

The `Dockerfile` builds on `python:3.13-slim` and is ordered to maximise layer
cache reuse:

```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first — this layer is cached unless requirements.txt changes.
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN SECRET_KEY=build-only python manage.py collectstatic --noinput

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
```

Key decisions:

- **Dependency layer caching** — `requirements.txt` is copied and installed
  *before* the application source. Because Docker invalidates a layer only when
  its inputs change, day-to-day code edits do not re-trigger the slow
  `pip install` step; it is reused until the dependency list itself changes.
- **Slim base + `--no-cache-dir`** — `python:3.13-slim` omits the build
  toolchain and docs that ship with the full image, and discarding the pip cache
  keeps the layer small. `psycopg2-binary` is used rather than `psycopg2`
  precisely so no compiler is needed at build time.
- **Non-root user** — the container runs as `appuser`, reducing the blast radius
  of a compromise.
- **Static files** — `collectstatic` runs at build time. A throwaway
  `SECRET_KEY` is supplied for that command only, because Django needs to import
  settings; it is not baked into the image's runtime environment.
- **Entrypoint** — [`entrypoint.sh`](entrypoint.sh) applies migrations, then
  `exec`s gunicorn, a production WSGI server, with a configurable worker count.
  Using `exec` means gunicorn becomes PID 1 and receives container stop signals
  directly, so shutdowns are graceful.

A `.dockerignore` keeps the build context lean by excluding the virtualenv, VCS
metadata, the local SQLite database, the manifests, the chart and the docs.

For local development, `docker-compose.yml` builds this same image and runs it
alongside a `postgres:17.5` container:

- the app service publishes port `8000` and receives `DEVELOPMENT_MODE=false`
  plus the database credentials, which switches it onto PostgreSQL;
- `DATABASE_HOST` is set to `db`, the service name — Compose's built-in DNS
  resolves it to the database container, so no IP addresses are hardcoded;
- the app waits on a `pg_isready` health check via
  `depends_on: condition: service_healthy`, so it does not race the database
  during startup;
- a named volume, `pg_data`, is mounted at the PostgreSQL data directory so the
  catalogue survives `docker compose down`.

---

## 4. How the CI/CD Pipeline Works

The pipeline is a single GitHub Actions workflow
(`.github/workflows/ci-cd.yml`) that runs on every push and pull request to
`main`. It is a **fan-out / fan-in** graph: four independent verification jobs
run in parallel, the build job waits on all of them, and the deploy job waits on
the build.

| Job | Runs when | What it does |
| --- | --- | --- |
| `test` | every push & PR | Runs the test suite |
| `runmigrations` | every push & PR | Applies migrations, proving they run cleanly from scratch |
| `migrations-check` | every push & PR | `makemigrations --check` — fails if a model was changed without generating a migration |
| `helm-lint` | every push & PR | `helm lint` plus a full template render of the chart |
| `build-docker-image` | push to `main` only | Builds with Buildx and pushes to GHCR |
| `deploy` | push to `main` only | `helm upgrade --install`, then verifies the rollout |

The four checks share a local composite action,
`.github/actions/install-dependencies`, which sets up Python and installs
requirements with pip caching — so the setup exists in one place rather than
being copy-pasted into each job.

Design choices worth highlighting:

- **Fail fast, in parallel.** The four checks have no dependency on one another,
  so running them concurrently gives the shortest path to a red build. Nothing is
  built or deployed unless all of them pass.
- **`makemigrations --check` as a guard.** This is the check that catches the
  most common Django mistake — editing a model and forgetting the migration. The
  drift is caught in CI rather than at deploy time, when it would break a rollout.
- **Lint the chart, not just the code.** A malformed template would otherwise
  only surface during `helm upgrade`, after an image had already been published.
- **PRs validate without publishing.** `build-docker-image` is gated on
  `github.ref == 'refs/heads/main'`, so a pull request is fully verified without
  touching the registry or the cluster.
- **Image published to GHCR** using the built-in `GITHUB_TOKEN`, so there are no
  long-lived registry credentials to store or rotate. The image name is derived
  from `github.repository`, so it follows the repo rather than being hardcoded.
- **`docker/metadata-action`** derives image tags and OCI labels from the git
  context, so published images carry their provenance instead of being tagged by
  hand. Buildx layer caching via `type=gha` keeps rebuilds cheap.
- **Graceful deploy skip.** The `secrets` context is not available in a job-level
  `if`, so the deploy job checks for `KUBE_CONFIG` in its first step and gates
  every cluster step on the result. Without the secret it logs a notice and
  skips, keeping the pipeline green on forks and before a cluster exists.
- **Automatic deployment on merge.** A push to `main` promotes an image all the
  way to the cluster, with the freshly-built tag injected into the chart via
  `--set`.

---

## 5. Kubernetes Deployment

The application is deployed two ways: a Helm chart in `charts/book-catalog/`,
which is what CI uses, and the equivalent plain manifests in `k8s/` for
inspecting the objects without templating.

From one `helm upgrade --install` the chart creates:

| Object | Purpose |
| --- | --- |
| `Deployment` | Two app replicas, readiness and liveness probes on `/health/`, CPU and memory requests and limits |
| `Service` (ClusterIP) | Stable in-cluster address in front of the pods |
| `Ingress` | Exposes the API at a hostname via the nginx ingress class (toggleable, TLS-ready) |
| `ConfigMap` | Non-sensitive configuration — debug flag, allowed hosts, database name/host/user |
| `Secret` | Django secret key and database password |
| PostgreSQL (optional) | Single-replica Deployment + Service + PersistentVolumeClaim for demo clusters |

How a deployment flows:

1. The app container receives all its configuration through `envFrom`, pulling
   every key from the ConfigMap and Secret — so the image itself carries no
   environment-specific data.
2. A helper template resolves the database host: the in-chart PostgreSQL Service
   by default, or an external host when `config.databaseHost` is set. Setting
   `postgresql.enabled=false` drops the in-cluster database entirely.
3. The pod template is annotated with SHA-256 checksums of the ConfigMap and
   Secret. A configuration change changes the checksum, which changes the pod
   template, which triggers a rolling restart — so pods always run with current
   config. Kubernetes does not do this on its own.
4. On startup each pod applies migrations via the image's entrypoint before
   serving traffic.
5. `helm upgrade --install --wait` makes the deploy idempotent and blocks until
   the new pods are healthy; the pipeline then confirms with
   `kubectl rollout status`.

The whole arrangement rests on labels: the Deployment's pod template carries
them, the Service selects on them rather than on pod names, and the Ingress names
the Service. That indirection is what lets pods be replaced freely — during a
rollout or after a crash — without anything upstream being reconfigured.

Because the app and the database are both part of one release, they share the
`name` and `instance` labels. An `app.kubernetes.io/component` label
distinguishes them, which matters: without it the app's Service selector would
also match the PostgreSQL pod and route API traffic to the database.

The image repository, tag and both secrets are supplied at install time with
`--set`, which is exactly how the pipeline injects the freshly-built image tag
and the deployment secrets. This keeps the chart generic and reusable across
environments.

---

## 6. Version Control Approach

### Branching

Work was done on a `development` branch and merged into `main` through
**pull request #1**, rather than committing straight to `main`. Even with a
single contributor this was worth the small overhead:

- the PR gives CI a chance to validate the change *before* it reaches `main`,
  which is what makes a branch-protection rule meaningful later;
- the merge commit records a reviewable unit of work, so the history describes
  intent and not just a sequence of edits;
- it matches how the project would be run with more contributors, so no habit
  has to be unlearned.

### Commit messages

Commits use short, imperative subject lines describing the change
(`Add book model and serializers with validation`,
`Implement book API with CRUD operations and configure CI/CD pipeline`,
`Refactor CI/CD workflow to streamline testing and migration steps`).

The brief made Conventional Commits optional. They were not adopted here: with
no changelog generation or semantic-version automation in the project, the
prefixes would add format discipline without yet buying the automation that
justifies them. Descriptive imperative subjects already make the history
readable. Were release automation added, switching would be worthwhile —
`feat:` / `fix:` prefixes are what those tools parse to decide version bumps.

---

## 7. Lessons Learned & Challenges

### Challenges faced

**One codebase, several environments.** The main design challenge was making a
single Django configuration work on a laptop, in Docker Compose and in a
cluster. Reading the database configuration from environment variables — with
SQLite as a zero-configuration fallback and PostgreSQL whenever
`DEVELOPMENT_MODE` is false — solved this without branching on environment names
in code.

**Container-to-container networking.** The app could not initially reach the
database: `localhost` inside the app container is the app container. The fix was
to set `DATABASE_HOST` to the Compose service name, `db`, and let Compose's DNS
resolve it — a reminder that each container has its own network namespace.

**Migrations drifting from models.** Editing a model without generating a
migration produces an error only later, when a query hits a column that does not
exist. Adding a dedicated `makemigrations --check` job turned a latent runtime
failure into an immediate CI failure.

**Labels and selectors in Kubernetes.** A Service whose selector does not match
the Deployment's pod-template labels reports no error — it simply routes to
nothing, and the failure looks like a networking problem. The mirror-image
mistake bit harder: because the app and PostgreSQL are one Helm release, they
shared the `name` and `instance` labels, so the app's Service selector *also*
matched the database pod. A selector that is too broad fails as quietly as one
that is too narrow. Adding a `component` label fixed it.

**Ordering inside the serializer.** Stripping ISBN separators in `validate_isbn`
looked correct and passed the obvious tests, but DRF runs field validators before
that hook — so a hyphenated duplicate slipped past the uniqueness check and only
failed at the database. Moving normalisation into `to_internal_value` fixed it.
The lesson is that "where" validation runs matters as much as "what" it checks.

**Reusing a step across jobs.** Four jobs need identical setup. Factoring this
into a composite action keeps it in one place, but the action was referenced
before it was written, so every job failed at its first step. A workflow that
reads correctly can still be broken; only the run log settles it.

**Migrating a model that already has rows.** Adding `auto_now_add` timestamps to
an existing table needs a value for the rows already there. Django's generated
migration wants a one-off default, and getting `django.utils.timezone.now` into
it — rather than an accidental literal — was a reminder to read generated
migrations rather than trust them blindly.

### Key lessons

- **Environment-driven configuration is the linchpin** of portability between
  local, container and cluster.
- **Build incrementally and commit often** — a layered history makes the system
  easier to reason about and to document.
- **A pipeline is only as good as its last green run.** A workflow that looks
  correct can still be broken; the run log is the source of truth.
- **CI should encode the mistakes you actually make.** The
  `makemigrations --check` job exists because migration drift is easy to cause
  and expensive to discover late.
- **Kubernetes is loosely coupled by design**, and that coupling is by label.
  Debugging means checking selectors, not just pod health — and checking that
  they are neither too narrow nor too broad.
- **Validation belongs in the serializer**, where it produces clear `400`
  responses close to the API boundary.
- **Helm turns a pile of manifests into one deployable unit**, and templating
  (`--set`, helpers, checksums) is what makes it reusable across environments.

---

## 8. Possible Future Improvements

The brief's requirements are met. These are the next things worth doing:

**Serve static assets with WhiteNoise.** `collectstatic` runs at build time, but
gunicorn does not serve the collected files, so the Django admin is unstyled
behind the API. WhiteNoise (or a sidecar) would close this.

**Add authentication and authorisation.** Every endpoint is currently open. Write
operations in particular should require an authenticated user.

**Enforce TLS end to end.** `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` and
`SECURE_HSTS_SECONDS` are wired to environment variables but default to off so
local HTTP development keeps working. Once the ingress terminates TLS they should
be switched on, and `SECURE_SSL_REDIRECT` added.

**Add a Horizontal Pod Autoscaler and a PodDisruptionBudget** to the chart, so
the service scales with load and survives node drains.

**Introduce staging and production values files** with environment promotion,
rather than passing everything through `--set`.

**Validate the ISBN checksum**, not just its length. A 13-digit string that is
not a real ISBN is currently accepted.

**Move the raw manifests' Secret out of version control.** `k8s/secret.yaml`
holds placeholders; a real deployment should use a sealed secret or an external
secrets operator. The Helm path already takes its secrets from CI at install
time.

---

## 9. Conclusion

The Book Catalog API delivers a fully-tested REST service that is containerized,
continuously integrated, and deployable to Kubernetes with a single Helm command
— with every stage automated from a push to `main`. Full CRUD over a validated
`Book` model, 15 passing tests, a hardened non-root image running gunicorn, a
Compose stack against real PostgreSQL, a six-job gated pipeline, and a
parameterised chart that packages the whole application as one release.

Beyond meeting the functional brief, the project demonstrates the practices that
make delivery repeatable and safe: environment-driven configuration, fast
automated tests, cache-efficient images, a pipeline that fails cheaply and early,
and a chart reusable across environments.

The exercise reinforced that the interesting problems in delivery are rarely in
the application code. Writing CRUD endpoints was the most straightforward part;
the parts that demanded real thought were making one configuration serve several
environments, getting containers to find each other, getting label selectors
precise enough to route correctly, and designing a pipeline that fails for the
right reasons at the right time.
