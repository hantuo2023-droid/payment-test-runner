import "./globals.css";
export const metadata = {
  title: "Payment Test Runner",
  description: "简单、清晰的浏览器自动化测试工作台",
};
export default function Layout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
