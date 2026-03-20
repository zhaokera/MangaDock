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
- B站动漫 (video.bilibili.com)

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

# 下载动漫视频
python main.py <video_url>
```

## 测试
```bash
pytest test/
```

## 更新日志

### v1.1.0 (2026-03-20)
- feat: 新增 B站动漫视频下载支持
- feat: 支持 BV/AV 号识别
- feat: 添加视频信息获取和播放地址解析

### v1.0.0 (2026-03-20)
- refactor: 移除重复代码，创建共享工具模块
 
