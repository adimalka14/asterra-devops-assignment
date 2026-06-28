{{- define "common.fullname" -}}
{{ .Release.Name }}-{{ .Chart.Name }}
{{- end }}

{{- define "common.labels" -}}
app: {{ include "common.fullname" . }}
version: {{ .Chart.AppVersion }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
managed-by: {{ .Release.Service }}
{{- end }}

{{- define "common.selectorLabels" -}}
app: {{ include "common.fullname" . }}
{{- end }}

{{- define "common.resources" -}}
resources:
  requests:
    cpu: {{ .Values.resources.requests.cpu }}
    memory: {{ .Values.resources.requests.memory }}
  limits:
    cpu: {{ .Values.resources.limits.cpu }}
    memory: {{ .Values.resources.limits.memory }}
{{- end }}