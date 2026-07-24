{{/* Base name for all resources. */}}
{{- define "book-catalog.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "book-catalog.fullname" -}}
{{- default .Release.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "book-catalog.labels" -}}
app.kubernetes.io/name: {{ include "book-catalog.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "book-catalog.selectorLabels" -}}
app.kubernetes.io/name: {{ include "book-catalog.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "book-catalog.postgresqlFullname" -}}
{{- printf "%s-postgresql" (include "book-catalog.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Resolve the database host: an explicit config.databaseHost wins, otherwise
fall back to the in-chart PostgreSQL service.
*/}}
{{- define "book-catalog.databaseHost" -}}
{{- if .Values.config.databaseHost -}}
{{- .Values.config.databaseHost -}}
{{- else -}}
{{- include "book-catalog.postgresqlFullname" . -}}
{{- end -}}
{{- end -}}
