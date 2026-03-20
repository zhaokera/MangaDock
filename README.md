# MangaDock - 漫画下载器

一个基于 Playwright 的漫画下载工具，支持多个漫画平台。

## 已支持平台
- 漫画柜 (manhuagui.com)
- 快看漫画 (kuaikanmanhua.com)
- B站漫画 (bilibili.com)
- 搜狗漫画 (sogou.dmzj.com)
- 番茄漫画 (tongjuemh.com)
- 纱雾漫画 (mh1234.com)
- Owining (owning.com)

## 特性
- 支持批量下载
- 支持进度跟踪
- 自动重试机制
- 并发下载优化

## 安装
```bash
pip install -r requirements.txt
```

## 使用
```bash
python main.py <url>
```

## 测试
```bash
pytest test/
```

## 更新日志

### v1.0.0 (2026-03-20)
- refactor: 移除重复代码，创建共享工具模块
