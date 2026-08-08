/**
 * 趣算算品牌Logo组件
 * 螺旋图案，象征宇宙运转、命运轮回与无限可能
 */

interface LogoProps {
  size?: number
  className?: string
  dark?: boolean // 是否使用深色主题（用于浅色背景）
}

export default function Logo({ size = 40, className = '', dark = false }: LogoProps) {
  // 生成螺旋路径点
  const generateSpiralPoints = () => {
    const points: string[] = []
    const centerX = 50
    const centerY = 50
    const startRadius = 8
    const endRadius = 48
    const rotations = 4
    const steps = 100
    
    for (let i = 0; i <= steps; i++) {
      const t = i / steps
      const angle = t * rotations * Math.PI * 2
      const radius = startRadius + (endRadius - startRadius) * t
      const x = centerX + Math.cos(angle) * radius
      const y = centerY + Math.sin(angle) * radius
      points.push(`${x},${y}`)
    }
    
    return points.join(' ')
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* 螺旋渐变 - 根据主题选择颜色 */}
      <defs>
        <linearGradient id="spiralGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          {dark ? (
            <>
              {/* 浅色背景 - 深棕色系，更明显 */}
              <stop offset="0%" stopColor="#3E2723" />
              <stop offset="50%" stopColor="#795548" />
              <stop offset="100%" stopColor="#3E2723" />
            </>
          ) : (
            <>
              {/* 深色背景 - 暖棕色渐变，替代金色 */}
              <stop offset="0%" stopColor="#A1887F" />
              <stop offset="50%" stopColor="#D7CCC8" />
              <stop offset="100%" stopColor="#A1887F" />
            </>
          )}
        </linearGradient>
        {/* 阴影效果 */}
        <filter id="logoShadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="0" stdDeviation="2" floodOpacity="0.3" />
        </filter>
      </defs>
      
      {/* 主螺旋路径 */}
      <polyline
        points={generateSpiralPoints()}
        fill="none"
        stroke="url(#spiralGradient)"
        strokeWidth="6"
        strokeLinecap="round"
        filter="url(#logoShadow)"
      />
      
      {/* 中心点 */}
      <circle cx="50" cy="50" r="5" fill={dark ? '#795548' : '#D7CCC8'} filter="url(#logoShadow)" />
    </svg>
  )
}
