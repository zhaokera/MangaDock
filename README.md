# MangaDock - 漫画/动漫下载器

一个基于 Playwright 的漫画和动漫下载工具，支持多个漫画和视频平台。

## 已支持平台

### 漫画平台
- 漫画柜 (manhuagui.com)
- 快看漫画 (kuaikanmanhua.com)
- B站漫画 (manga.bilibili.com)
- 搜狗漫画 (sogou.dmzj.com)
- 番茄漫画 (tongjuemh.com)
- 纱雾漫画 (mh1234.com)
- Owining (owning.com)

### 动漫视频平台
- B站视频 (video.bilibili.com)
- 腾讯视频 (v.qq.com)
- 爱奇艺 (iqiyi.com)
- 优酷 (youku.com)
- 芒果TV (mgtv.com)

## 特性
- 支持批量下载
- 支持进度跟踪
- 自动重试机制
- 并发下载优化
- 视频格式自动识别
- **按名称搜索视频** - 无需输入 URL，直接搜索动漫名称即可下载

## 特性
- 支持批量下载
- 支持进度跟踪
- 自动重试机制
- 并发下载优化
- 视频格式自动识别

## 安装
```bash
pip install -r requirements.txt
```

## 使用
```bash
# 下载漫画
python main.py <comic_url>

# 下载动漫视频（通过 URL）
python main.py <video_url>

# 通过名称搜索视频（新增）
python main.py --search "灌篮高手" --platform tencent
```

### API 使用

#### 搜索视频
```bash
# 搜索所有平台
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "海贼王", "limit": 10}'

# 搜索特定平台
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "海贼王", "platform": "tencent", "limit": 10}'
```

## 测试
```bash
pytest test/
```

## 更新日志

### v1.2.0 (2026-03-20)
- feat: 新增按名称搜索视频功能
- feat: 支持腾讯视频、爱奇艺、优酷、芒果TV搜索
- feat: 添加 `/api/search` API 端点

### v1.1.0 (2026-03-20)
- feat: 新增 B站动漫视频下载支持
- feat: 支持 BV/AV 号识别
- feat: 添加视频信息获取和播放地址解析

### v1.0.0 (2026-03-20)
- refactor: 移除重复代码，创建共享工具模块
 
