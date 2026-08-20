type EvidenceStatusProps = {
  evidenceIds: string | string[]
  label?: string
}

export function EvidenceStatus({ evidenceIds, label = '数据已核验' }: EvidenceStatusProps) {
  const ids = Array.isArray(evidenceIds) ? evidenceIds : [evidenceIds]
  const traceText = ids.map((id) => `#${id}`).join('、')

  return (
    <span
      className="evidence-status"
      title={`可追溯至查询记录 ${traceText}`}
      aria-label={`${label}，可追溯至 ${ids.length} 条查询记录`}
    >
      <span aria-hidden="true">✓</span>
      {label}
    </span>
  )
}
