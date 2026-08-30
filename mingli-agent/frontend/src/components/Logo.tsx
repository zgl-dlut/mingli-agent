/**
 * 趣算算品牌Logo组件
 * showText=false：渲染棕色圆形 + "趣"字（用于头像/图标）
 * showText=true：渲染"趣算算"文字
 */

interface LogoProps {
  className?: string
  dark?: boolean // 兼容旧调用，当前不影响渲染
  showText?: boolean // 是否显示"趣算算"文字，默认显示
}

export default function Logo({ className = '', dark: _dark = false, showText = true }: LogoProps) {
  if (!showText) {
    // 图标模式：棕色圆形 + "趣"字
    return (
      <div
        className={`logo-icon-circle ${className}`}
        style={{
          backgroundColor: '#8b6f5a',
          color: '#f4f2f0',
          width: 36,
          height: 36,
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          fontWeight: 700,
          fontFamily: '"思源黑体圆角", "PingFang SC", system-ui, sans-serif',
          flexShrink: 0,
        }}
      >
        趣
      </div>
    )
  }
  // 文字模式
  return (
    <div className={`header-logo ${className}`}>
      <span className="logo-text">趣算算</span>
    </div>
  )
}
