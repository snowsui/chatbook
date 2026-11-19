# 字体（不随仓库分发，自己下载）

页面用三种开源字体（都是 SIL Open Font License 1.1，可免费商用、可子集化内嵌）：

| config.fonts 键 | 用途 | 字体 | 下载 |
|---|---|---|---|
| `ink` | 正文、标题（宋体） | Noto Serif SC（思源宋体），推荐可变字重版 `NotoSerifSC-VF.otf` | https://github.com/notofonts/noto-cjk/tree/main/Serif/Variable/OTF/Subset （或 https://fonts.google.com/noto/specimen/Noto+Serif+SC ） |
| `hand` | 导语、摘要、对话（楷体） | 霞鹜文楷 LXGW WenKai，`LXGWWenKai-Regular.ttf` | https://github.com/lxgw/LxgwWenKai/releases |
| `brush` | 竖排大标题、印章（书法） | 马善政 Ma Shan Zheng，`MaShanZheng-Regular.ttf` | https://fonts.google.com/specimen/Ma+Shan+Zheng （源文件 https://github.com/google/fonts/tree/main/ofl/mashanzheng ） |

下载后放在任意位置，在项目的 `chronicle.config.json` 里写路径（相对项目目录或绝对路径）：

```json
"fonts": {"ink": "fonts/NotoSerifSC-VF.otf", "hand": "fonts/LXGWWenKai-Regular.ttf", "brush": "fonts/MaShanZheng-Regular.ttf"}
```

- 构建脚本只把页面里实际用到的字做成子集（woff2，需要 `pip install fonttools brotli`），单页一般几百 KB 到 1–2 MB。
- 哪个键没配、文件不存在或没装 fontTools，就不嵌入那种字体，页面退回系统字体（宋体/楷体），排版不变。
- 聊天原文片段始终用系统无衬线字体，不进子集。
