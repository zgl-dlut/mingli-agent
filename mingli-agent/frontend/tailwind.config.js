/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 已废弃的棕色 primary 色阶，保留为占位避免编译报错，全站不再使用
        primary: {
          50: '#fdf8f6',
          100: '#f2e8e5',
          200: '#eaddd7',
          300: '#e0cec7',
          400: '#d2bab0',
          500: '#bfa094',
          600: '#a18072',
          700: '#977669',
          800: '#846358',
          900: '#6f5149',
        },
        /**
         * brand 品牌色 —— 统一映射到 src/theme/tokens.ts 定义的黛蓝紫主色系。
         *
         * 历史棕色体系（#8b6f5a / #a7876f）已全部替换为以下色值，
         * 硬编码十六进制也统一迁移到 tokens 定义。禁止再引入棕色。
         */
        brand: {
          // 背景色阶
          bg: '#F7F5F0',           // 页面底层背景 / 历史条目卡片（color.bg）
          bgInput: '#FFFFFF',      // 输入框底色（color.card）
          bgCard: '#FFFFFF',       // 对话框/结果卡片背景（color.card）
          bgHistory: '#F7F5F0',    // 历史页整体底层背景（color.bg）
          // 导航与按钮
          nav: '#4A4E8F',          // 主色 / Tab 选中 / 主 CTA（color.brand）
          cream: '#FFFFFF',        // 品牌按钮上的文字（白）
          button: '#4A4E8F',       // 按钮默认常态
          buttonHover: '#5A5FA8',  // 按钮悬浮（主色微亮）
          buttonActive: '#3E4278', // 按钮按下（主色微深，yearHero 起端）
          buttonText: '#FFFFFF',   // 按钮文字
          // 文字色阶（墨色）
          brown: '#2B2B33',        // 正文普通文字（color.ink，保留历史名但值已换墨色）
          brownStrong: '#2B2B33',  // 板块加粗标题（color.ink）
          muted: '#8A8A93',        // 次要说明小字（color.ink2）
          // 装饰与边框
          gold: '#C9A86A',         // 金色点缀（color.gold）
          inputBorder: '#F0EEE7',  // 分割线/输入框边框（color.divider）
          closeBtn: '#8A8A93',     // 弹窗关闭按钮
          overlay: 'rgba(43, 43, 51, 0.35)', // 弹窗遮罩（墨色半透明）
          // 兼容旧引用
          dark: '#4A4E8F',
          light: '#EEEFF9',        // 主色 soft 底（color.brandSoft）
          goldHover: '#5A5FA8',
          warn: '#D9772B',         // 警示档（color.warn）
          bgDark: '#2B2B33',
          navDark: '#3E4278',
          cardDark: '#3E4278',
          textDark: '#EEEFF9',
        },
        gold: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
