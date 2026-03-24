# 漫画下载器性能优化补丁

## 主要优化点

### 1. 浏览器实例复用
**问题**: 每次下载都启动新浏览器实例
**解决方案**: 创建浏览器池，复用实例

### 2. 减少等待时间
**问题**: 多处不必要的长等待
**解决方案**: 
- 将 `wait_for_timeout(2000)` 减少到 `wait_for_timeout(500)`
- 使用智能等待条件替代固定等待

### 3. 增加并发数
**问题**: 图片下载并发数限制为5
**解决方案**: 增加到10，并使用连接池

### 4. 优化重试策略
**问题**: 重试3次，每次500ms
**解决方案**: 减少到2次，每次200ms

## 具体代码修改

### 文件: crawlers/base.py

**修改 download_image 方法**:
```python
async def download_image(self, url: str, filepath: Path, headers: Optional[dict] = None, max_retries: int = 2) -> bool:
    # ... 重试次数从3改为2
    for attempt in range(1, max_retries + 1):
        # ... 等待时间从0.5秒改为0.2秒
        if attempt < max_retries:
            await asyncio.sleep(0.2)
```

**修改 download_image_via_browser 方法**:
```python
async def download_image_via_browser(self, url: str, filepath: Path, referer: str = "", max_retries: int = 2) -> bool:
    # ... 重试次数从3改为2
    for attempt in range(1, max_retries + 1):
        # ... 等待时间从0.5秒改为0.2秒
        if attempt < max_retries:
            await asyncio.sleep(0.2)
```

### 文件: crawlers/manhuagui.py

**修改 _do_download 方法中的等待时间**:
```python
# 原代码: await self.page.wait_for_timeout(2000)
# 修改为: await self.page.wait_for_timeout(500)

# 原代码: await self.page.wait_for_timeout(5000)  
# 修改为: await self.page.wait_for_timeout(1000)

# 原代码: await self.page.wait_for_timeout(3000)
# 修改为: await self.page.wait_for_timeout(800)
```

**修改并发数**:
```python
# 原代码: semaphore = asyncio.Semaphore(5)
# 修改为: semaphore = asyncio.Semaphore(10)
```

### 文件: server.py

**添加浏览器池管理**:
```python
# 在全局状态部分添加
browser_pool = []
BROWSER_POOL_SIZE = 2

class BrowserPool:
    def __init__(self):
        self.browsers = []
        self.lock = asyncio.Lock()
    
    async def get_browser(self):
        async with self.lock:
            if self.browsers:
                return self.browsers.pop()
            else:
                return await self._create_browser()
    
    async def return_browser(self, browser):
        async with self.lock:
            if len(self.browsers) < BROWSER_POOL_SIZE:
                self.browsers.append(browser)
            else:
                await browser.close()
    
    async def _create_browser(self):
        # 创建浏览器实例的逻辑
        pass
```

## 预期性能提升

- **浏览器启动时间**: 从 ~3秒 减少到 ~0秒 (复用)
- **页面等待时间**: 从 ~10秒 减少到 ~2秒
- **图片下载时间**: 从 ~5秒 减少到 ~3秒 (更高并发)
- **总下载时间**: 预计减少 50-60%

## 风险评估

1. **内存使用增加**: 浏览器池会占用更多内存
2. **稳定性风险**: 更高的并发可能导致服务器压力
3. **兼容性**: 需要测试不同网站的兼容性

## 测试计划

1. 使用测试URL: `https://www.manhuagui.com/comic/14798/146582.html`
2. 对比优化前后的下载时间
3. 监控内存和CPU使用情况
4. 验证图片完整性和质量