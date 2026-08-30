interface Version {
  id: number
  name: string
  created_at: string
}

interface VersionSelectorProps {
  versions: Version[]
  selectedVersion: number
  compareVersion?: number
  onSelect: (versionId: number) => void
  onCompare?: (versionId1: number, versionId2: number) => void
  showCompare?: boolean
}

export default function VersionSelector({
  versions,
  selectedVersion,
  compareVersion,
  onSelect,
  onCompare,
  showCompare = false,
}: VersionSelectorProps) {
  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-600">版本:</span>
      <select
        value={selectedVersion}
        onChange={(e) => onSelect(Number(e.target.value))}
        className="px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        style={{ width: 200 }}
      >
        {versions.map(v => (
          <option key={v.id} value={v.id}>
            {v.name} ({formatTime(v.created_at)})
          </option>
        ))}
      </select>
      {showCompare && (
        <>
          <span className="text-sm text-gray-600 ml-2">对比:</span>
          <select
            value={compareVersion || ''}
            onChange={(e) => {
              const val = e.target.value
              if (val) onCompare?.(selectedVersion, Number(val))
            }}
            className="px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            style={{ width: 200 }}
          >
            <option value="">选择对比版本</option>
            {versions
              .filter(v => v.id !== selectedVersion)
              .map(v => (
                <option key={v.id} value={v.id}>
                  {v.name} ({formatTime(v.created_at)})
                </option>
              ))}
          </select>
        </>
      )}
    </div>
  )
}
