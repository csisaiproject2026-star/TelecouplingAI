const { marked } = require('marked');
const fs = require('fs');
const path = require('path');

const mdFile = process.argv[2];
const mdContent = fs.readFileSync(mdFile, 'utf-8');
const htmlBody = marked.parse(mdContent);

// 把图片路径中的反斜杠统一（Windows兼容）
// 图片相对路径 demo_screenshots/xx.png → 直接嵌入base64，确保HTML独立可用
const dir = path.dirname(mdFile);

// 替换所有 <img src="..."> 为 base64 内嵌
const htmlWithImages = htmlBody.replace(/<img src="([^"]+)"/g, (match, src) => {
  const imgPath = path.join(dir, src);
  if (fs.existsSync(imgPath)) {
    const ext = path.extname(imgPath).slice(1).toLowerCase();
    const mime = ext === 'png' ? 'image/png' : ext === 'jpg' ? 'image/jpeg' : 'image/png';
    const b64 = fs.readFileSync(imgPath).toString('base64');
    return `<img style="max-width:100%;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,0.15);margin:12px 0;" src="data:${mime};base64,${b64}"`;
  }
  return match;
});

const html = `<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CSIS 用户演示流程</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 960px; margin: 40px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.7; }
  h1 { color: #1a56db; border-bottom: 3px solid #1a56db; padding-bottom: 12px; }
  h2 { color: #1e429f; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-top: 40px; }
  h3 { color: #374151; margin-top: 28px; }
  blockquote { background: #f0f4ff; border-left: 4px solid #1a56db; margin: 0; padding: 12px 16px; border-radius: 0 8px 8px 0; color: #374151; }
  code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
  pre { background: #1f2937; color: #f9fafb; padding: 16px; border-radius: 8px; overflow-x: auto; }
  pre code { background: none; padding: 0; color: inherit; }
  table { border-collapse: collapse; width: 100%; margin: 16px 0; }
  th { background: #1a56db; color: white; padding: 10px 14px; text-align: left; }
  td { padding: 9px 14px; border-bottom: 1px solid #e5e7eb; }
  tr:nth-child(even) td { background: #f9fafb; }
  input[type=checkbox] { margin-right: 6px; }
  li { margin: 4px 0; }
  hr { border: none; border-top: 2px solid #e5e7eb; margin: 32px 0; }
  strong { color: #111; }
  img { display: block; }
  p > img { margin: 16px 0; }
</style>
</head>
<body>
${htmlWithImages}
</body>
</html>`;

const outFile = mdFile.replace(/\.md$/, '.html');
fs.writeFileSync(outFile, html, 'utf-8');
console.log(`✅ 生成完成: ${outFile}`);
console.log(`   文件大小: ${(fs.statSync(outFile).size / 1024 / 1024).toFixed(1)} MB`);
