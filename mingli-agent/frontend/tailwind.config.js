/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
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
        brand: {
          // 背景色阶（低饱和灰褐棕，由浅至深）
          bg: '#f2f0ed',           // 首页底层背景 / 历史条目卡片
          bgInput: '#F3EFEA',      // 输入框底色
          bgCard: '#eceae6',       // 对话框/结果卡片背景（不带棕）
          bgHistory: '#e9e7e3',    // 历史页整体底层背景
          // 导航与按钮（吸取Cursor导航灰褐棕）
          nav: '#8b6f5a',          // 顶部导航栏底色 / 按钮按下色
          cream: '#f4f2f0',        // 导航栏文字 / 暖灰白
          button: '#a7876f',       // 按钮默认常态
          buttonHover: '#997c63',  // 按钮悬浮
          buttonActive: '#8b6f5a', // 按钮按下
          buttonText: '#f4f2f0',   // 按钮文字
          // 文字色阶（暖炭灰系）
          brown: '#44403d',        // 正文普通文字
          brownStrong: '#363330',  // 板块加粗标题
          muted: '#615c59',        // 次要说明小字
          // 装饰与边框
          gold: '#C9B5A1',         // 星星装饰图标 / 哑光驼色
          inputBorder: '#d8d4d0',  // 分割线/输入框边框 / 浅冷灰
          closeBtn: '#645952',     // 弹窗关闭按钮
          overlay: 'rgba(50, 44, 40, 0.28)', // 弹窗遮罩
          // 兼容旧引用
          dark: '#8b6f5a',
          light: '#f2f0ed',
          goldHover: '#997c63',
          warn: '#a86c50',
          bgDark: '#3b2b24',
          navDark: '#44403d',
          cardDark: '#4c3b33',
          textDark: '#c2b0a6',
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
