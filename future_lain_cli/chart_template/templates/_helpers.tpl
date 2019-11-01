{{/* vim: set filetype=mustache: */}}

{{- define "chart.image" -}}
{{- printf "%s/%s:%s" .Values.registry .Values.appname .Values.imageTag}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}

{{/*
Common labels
*/}}
{{- define "chart.labels" -}}
helm.sh/chart: {{ .Values.appname }}
{{ include "chart.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels
*/}}
{{- define "chart.selectorLabels" -}}
app.kubernetes.io/name: {{ .Values.appname }}
{{- end -}}
